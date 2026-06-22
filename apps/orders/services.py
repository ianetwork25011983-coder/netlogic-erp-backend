"""
Motor de Pedidos Web (Módulo 8).

`OrderService.crear_pedido()` resuelve precios desde la lista indicada
(o `Producto.precio` si el producto no está en la lista), aplica
promociones vigentes automáticamente, aplica el cupón si se indica, y
reserva stock vía `InventoryService.reservar_stock` -- sin generar
movimiento de Kardex todavía. Recién al facturar (`facturar_pedido`) se
libera la reserva y se genera la salida real de stock, a través de
`BillingService.emitir_documento`.
"""
import datetime
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.billing.services import BillingError, BillingService
from apps.inventory.services import InsufficientStockError, InventoryService

from .models import HistorialEstadoPedido, PedidoWeb, PedidoWebItem

CENTS = Decimal("0.01")


class OrderError(Exception):
    pass


class OrderService:
    REFERENCIA_TIPO = "PEDIDO_WEB"

    @staticmethod
    def _siguiente_numero(empresa):
        ultimo = PedidoWeb.objects.filter(empresa=empresa).order_by("-id").first()
        siguiente = (ultimo.id + 1) if ultimo else 1
        return f"PED-{empresa.id:03d}-{siguiente:06d}"

    @staticmethod
    def _registrar_historial(pedido, estado_anterior, estado_nuevo, usuario=None, nota=""):
        HistorialEstadoPedido.objects.create(
            pedido=pedido, estado_anterior=estado_anterior, estado_nuevo=estado_nuevo, usuario=usuario, nota=nota,
        )

    @staticmethod
    def _resolver_precio(producto, lista_precio, fecha):
        precio_item = lista_precio.precios.filter(producto=producto).first()
        precio_base = precio_item.precio if precio_item else producto.precio

        descuento_promocion = Decimal("0")
        for promo in producto.promociones.filter(active=True):
            if promo.vigente(fecha) and promo.descuento_porcentaje > descuento_promocion:
                descuento_promocion = promo.descuento_porcentaje

        from apps.pricing.models import Promocion

        if producto.categoria_id:
            promo_categoria = Promocion.objects.filter(
                categoria_id=producto.categoria_id, active=True,
                vigencia_desde__lte=fecha, vigencia_hasta__gte=fecha,
            ).order_by("-descuento_porcentaje").first()
            if promo_categoria and promo_categoria.descuento_porcentaje > descuento_promocion:
                descuento_promocion = promo_categoria.descuento_porcentaje

        return precio_base, descuento_promocion

    # ------------------------------------------------------------------
    # Creación + validación + reserva
    # ------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def crear_pedido(
        cls, *, empresa, sucursal, cliente, lista_precio, deposito_reserva, items_data,
        portal_user=None, cupon_code=None, observaciones="", fecha=None,
    ):
        """
        `items_data`: lista de dicts {"producto_id", "cantidad"}.
        El precio se resuelve automáticamente desde la lista de precios +
        promociones vigentes; no se recibe precio_unitario del cliente.
        """
        from apps.products.models import Producto

        fecha = fecha or datetime.date.today()

        pedido = PedidoWeb.objects.create(
            empresa=empresa, sucursal=sucursal, numero=cls._siguiente_numero(empresa), cliente=cliente,
            portal_user=portal_user, lista_precio=lista_precio, deposito_reserva=deposito_reserva,
            estado=PedidoWeb.ESTADO_PENDIENTE_VALIDACION, observaciones=observaciones,
        )
        cls._registrar_historial(pedido, "", pedido.estado, nota="Pedido creado desde carrito")

        subtotal = Decimal("0")
        items_creados = []
        for item_data in items_data:
            producto = Producto.objects.get(pk=item_data["producto_id"])
            cantidad = Decimal(item_data["cantidad"])
            precio_base, descuento_pct = cls._resolver_precio(producto, lista_precio, fecha)

            subtotal_linea = (Decimal(cantidad) * Decimal(precio_base) * (1 - descuento_pct / 100)).quantize(
                CENTS, rounding=ROUND_HALF_UP
            )
            subtotal += subtotal_linea

            item = PedidoWebItem.objects.create(
                pedido=pedido, producto=producto, cantidad=cantidad, precio_unitario=precio_base,
                descuento_porcentaje=descuento_pct, subtotal_linea=subtotal_linea,
            )
            items_creados.append(item)

        descuento_cupon = Decimal("0")
        cupon_obj = None
        if cupon_code:
            from apps.pricing.models import Cupon

            cupon_obj = Cupon.objects.filter(empresa=empresa, codigo=cupon_code).first()
            if cupon_obj is None:
                raise OrderError(f"El cupón '{cupon_code}' no existe.")
            es_valido, motivo = cupon_obj.es_valido(fecha, subtotal)
            if not es_valido:
                raise OrderError(f"Cupón inválido: {motivo}")
            descuento_cupon = cupon_obj.calcular_descuento(subtotal).quantize(CENTS, rounding=ROUND_HALF_UP)

        pedido.cupon = cupon_obj
        pedido.subtotal = subtotal
        pedido.descuento_total = descuento_cupon
        pedido.total = subtotal - descuento_cupon
        pedido.save(update_fields=["cupon", "subtotal", "descuento_total", "total"])

        try:
            cls._reservar_items(pedido, items_creados)
        except InsufficientStockError as exc:
            estado_anterior = pedido.estado
            pedido.estado = PedidoWeb.ESTADO_RECHAZADO
            pedido.motivo_rechazo = str(exc)
            pedido.save(update_fields=["estado", "motivo_rechazo"])
            cls._registrar_historial(pedido, estado_anterior, pedido.estado, nota=str(exc))
            return pedido

        if cupon_obj:
            cupon_obj.usos_actuales += 1
            cupon_obj.save(update_fields=["usos_actuales"])

        estado_anterior = pedido.estado
        pedido.estado = PedidoWeb.ESTADO_VALIDADO
        pedido.save(update_fields=["estado"])
        cls._registrar_historial(pedido, estado_anterior, pedido.estado, nota="Stock reservado correctamente")

        return pedido

    @classmethod
    def _reservar_items(cls, pedido, items):
        for item in items:
            if not item.producto.descuenta_stock:
                continue
            InventoryService.reservar_stock(
                producto=item.producto, deposito=pedido.deposito_reserva, cantidad=item.cantidad,
                referencia_tipo=cls.REFERENCIA_TIPO, referencia_id=pedido.id,
            )

    # ------------------------------------------------------------------
    # Transiciones de estado
    # ------------------------------------------------------------------
    @classmethod
    def aprobar_pedido(cls, pedido, usuario, nota=""):
        if pedido.estado != PedidoWeb.ESTADO_VALIDADO:
            raise OrderError(f"Solo se puede aprobar un pedido VALIDADO (estado actual: {pedido.estado}).")
        estado_anterior = pedido.estado
        pedido.estado = PedidoWeb.ESTADO_APROBADO
        pedido.save(update_fields=["estado"])
        cls._registrar_historial(pedido, estado_anterior, pedido.estado, usuario=usuario, nota=nota)
        return pedido

    @classmethod
    @transaction.atomic
    def rechazar_pedido(cls, pedido, motivo, usuario):
        if pedido.estado in (PedidoWeb.ESTADO_FACTURADO, PedidoWeb.ESTADO_DESPACHADO, PedidoWeb.ESTADO_ENTREGADO):
            raise OrderError("No se puede rechazar un pedido ya facturado.")
        InventoryService.liberar_reservas_de_referencia(cls.REFERENCIA_TIPO, pedido.id)
        estado_anterior = pedido.estado
        pedido.estado = PedidoWeb.ESTADO_RECHAZADO
        pedido.motivo_rechazo = motivo
        pedido.save(update_fields=["estado", "motivo_rechazo"])
        cls._registrar_historial(pedido, estado_anterior, pedido.estado, usuario=usuario, nota=motivo)
        return pedido

    @classmethod
    @transaction.atomic
    def cancelar_pedido(cls, pedido, motivo, usuario):
        if pedido.estado in (PedidoWeb.ESTADO_FACTURADO, PedidoWeb.ESTADO_DESPACHADO, PedidoWeb.ESTADO_ENTREGADO):
            raise OrderError("No se puede cancelar un pedido ya facturado; anule la factura en su lugar.")
        InventoryService.liberar_reservas_de_referencia(cls.REFERENCIA_TIPO, pedido.id)
        estado_anterior = pedido.estado
        pedido.estado = PedidoWeb.ESTADO_CANCELADO
        pedido.save(update_fields=["estado"])
        cls._registrar_historial(pedido, estado_anterior, pedido.estado, usuario=usuario, nota=motivo)
        return pedido

    @classmethod
    def marcar_en_picking(cls, pedido, usuario, nota=""):
        if pedido.estado != PedidoWeb.ESTADO_APROBADO:
            raise OrderError(f"Solo se puede iniciar picking de un pedido APROBADO (estado actual: {pedido.estado}).")
        estado_anterior = pedido.estado
        pedido.estado = PedidoWeb.ESTADO_EN_PICKING
        pedido.save(update_fields=["estado"])
        cls._registrar_historial(pedido, estado_anterior, pedido.estado, usuario=usuario, nota=nota)
        return pedido

    @classmethod
    @transaction.atomic
    def facturar_pedido(cls, pedido, *, punto_venta, usuario, condicion_venta="CONTADO"):
        if pedido.estado != PedidoWeb.ESTADO_EN_PICKING:
            raise OrderError(f"Solo se puede facturar un pedido EN_PICKING (estado actual: {pedido.estado}).")

        items_data = [
            {
                "producto_id": item.producto_id,
                "cantidad": item.cantidad,
                "precio_unitario": item.precio_unitario,
                "descuento_porcentaje": item.descuento_porcentaje,
            }
            for item in pedido.items.all()
        ]

        InventoryService.liberar_reservas_de_referencia(cls.REFERENCIA_TIPO, pedido.id)

        try:
            documento = BillingService.emitir_documento(
                empresa=pedido.empresa, sucursal=pedido.sucursal, punto_venta=punto_venta,
                tipo_documento="FACTURA", cliente=pedido.cliente, moneda_code=pedido.lista_precio.moneda.code,
                items_data=items_data, usuario=usuario, condicion_venta=condicion_venta,
                afecta_inventario=True, deposito_salida=pedido.deposito_reserva,
                observaciones=f"Generada desde Pedido Web {pedido.numero}",
                descuento_global=pedido.descuento_total,
            )
        except BillingError as exc:
            raise OrderError(str(exc)) from exc

        estado_anterior = pedido.estado
        pedido.estado = PedidoWeb.ESTADO_FACTURADO
        pedido.documento_venta = documento
        pedido.save(update_fields=["estado", "documento_venta"])
        cls._registrar_historial(pedido, estado_anterior, pedido.estado, usuario=usuario, nota=f"Factura {documento.numero}")

        return pedido

    @classmethod
    def marcar_despachado(cls, pedido, usuario, nota=""):
        if pedido.estado != PedidoWeb.ESTADO_FACTURADO:
            raise OrderError(f"Solo se puede despachar un pedido FACTURADO (estado actual: {pedido.estado}).")
        estado_anterior = pedido.estado
        pedido.estado = PedidoWeb.ESTADO_DESPACHADO
        pedido.save(update_fields=["estado"])
        cls._registrar_historial(pedido, estado_anterior, pedido.estado, usuario=usuario, nota=nota)
        return pedido

    @classmethod
    def marcar_entregado(cls, pedido, usuario, nota=""):
        if pedido.estado != PedidoWeb.ESTADO_DESPACHADO:
            raise OrderError(f"Solo se puede marcar entregado un pedido DESPACHADO (estado actual: {pedido.estado}).")
        estado_anterior = pedido.estado
        pedido.estado = PedidoWeb.ESTADO_ENTREGADO
        pedido.save(update_fields=["estado"])
        cls._registrar_historial(pedido, estado_anterior, pedido.estado, usuario=usuario, nota=nota)
        return pedido
