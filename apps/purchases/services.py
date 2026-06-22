"""
Servicio de Compras (Módulo 9).

`recibir_orden()` es el único punto de entrada que conecta Compras con
Inventario: por cada línea recibida llama a
`apps.inventory.services.InventoryService.registrar_entrada`, usando el
costo y moneda de la Orden de Compra. Así el Kardex/costeo FIFO-LIFO-
Promedio del Módulo 4 queda sincronizado automáticamente con cada
recepción de mercadería, sin que Compras necesite conocer los detalles
de costeo.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.inventory.services import InventoryService

from .models import (
    Cotizacion,
    OrdenCompra,
    OrdenCompraItem,
    RecepcionCompra,
    RecepcionCompraItem,
)


class PurchaseError(Exception):
    pass


class PurchaseService:
    # ------------------------------------------------------------------
    # Numeración correlativa simple por modelo/empresa.
    # ------------------------------------------------------------------
    @staticmethod
    def _siguiente_numero(modelo, empresa, prefijo):
        ultimo = modelo.objects.filter(empresa=empresa).order_by("-id").first()
        siguiente = (ultimo.id + 1) if ultimo else 1
        return f"{prefijo}-{empresa.id:03d}-{siguiente:06d}"

    @classmethod
    def generar_numero_orden_compra(cls, empresa):
        return cls._siguiente_numero(OrdenCompra, empresa, "OC")

    @classmethod
    def generar_numero_recepcion(cls, empresa_id):
        ultimo = RecepcionCompra.objects.order_by("-id").first()
        siguiente = (ultimo.id + 1) if ultimo else 1
        return f"REC-{siguiente:06d}"

    # ------------------------------------------------------------------
    # Comparación de cotizaciones (Módulo 9: "Comparar Proveedores, Costos, Plazos, Historial")
    # ------------------------------------------------------------------
    @staticmethod
    def comparar_cotizaciones(solicitud):
        """
        Devuelve una lista de dicts comparables por proveedor: total
        cotizado, plazo de entrega y condiciones de pago, ordenada por
        total ascendente (la más económica primero).
        """
        cotizaciones = solicitud.cotizaciones.filter(
            estado__in=[Cotizacion.ESTADO_RECIBIDA, Cotizacion.ESTADO_SELECCIONADA]
        ).select_related("proveedor", "moneda").prefetch_related("items")

        resultado = []
        for cot in cotizaciones:
            resultado.append({
                "cotizacion_id": cot.id,
                "proveedor": cot.proveedor.nombre_comercial or cot.proveedor.razon_social,
                "proveedor_id": cot.proveedor_id,
                "moneda": cot.moneda.code,
                "total": cot.total,
                "plazo_entrega_dias": cot.plazo_entrega_dias,
                "condiciones_pago": cot.condiciones_pago,
                "vigencia_hasta": cot.vigencia_hasta,
                "estado": cot.estado,
            })
        return sorted(resultado, key=lambda r: r["total"])

    # ------------------------------------------------------------------
    # Conversión Cotización -> Orden de Compra
    # ------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def crear_orden_desde_cotizacion(cls, cotizacion, sucursal, usuario, condiciones_pago=""):
        orden = OrdenCompra.objects.create(
            empresa=cotizacion.empresa,
            sucursal=sucursal,
            proveedor=cotizacion.proveedor,
            cotizacion=cotizacion,
            numero=cls.generar_numero_orden_compra(cotizacion.empresa),
            moneda=cotizacion.moneda,
            condiciones_pago=condiciones_pago or cotizacion.condiciones_pago,
            usuario=usuario,
        )
        items = [
            OrdenCompraItem(
                orden_compra=orden,
                producto=item.producto,
                cantidad=item.cantidad,
                precio_unitario=item.precio_unitario,
                descuento_porcentaje=item.descuento_porcentaje,
            )
            for item in cotizacion.items.all()
        ]
        OrdenCompraItem.objects.bulk_create(items)

        cotizacion.estado = Cotizacion.ESTADO_SELECCIONADA
        cotizacion.save(update_fields=["estado"])
        if cotizacion.solicitud_id:
            cotizacion.solicitud.estado = cotizacion.solicitud.ESTADO_CONVERTIDA
            cotizacion.solicitud.save(update_fields=["estado"])

        return orden

    # ------------------------------------------------------------------
    # Recepción de mercadería (conecta con InventoryService)
    # ------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def recibir_orden(cls, *, orden_compra, deposito, items_data, usuario, observaciones=""):
        """
        `items_data`: lista de dicts
            {"orden_compra_item_id": int, "cantidad_recibida": Decimal,
             "numero_lote": str opcional, "fecha_vencimiento": date opcional}
        """
        if orden_compra.estado == OrdenCompra.ESTADO_CANCELADA:
            raise PurchaseError("No se puede recibir mercadería de una orden cancelada.")

        recepcion = RecepcionCompra.objects.create(
            orden_compra=orden_compra,
            deposito=deposito,
            numero=cls.generar_numero_recepcion(orden_compra.empresa_id),
            usuario=usuario,
            observaciones=observaciones,
        )

        for data in items_data:
            oc_item = OrdenCompraItem.objects.select_for_update().get(
                pk=data["orden_compra_item_id"], orden_compra=orden_compra
            )
            cantidad = Decimal(data["cantidad_recibida"])
            if cantidad <= 0:
                raise PurchaseError("La cantidad recibida debe ser mayor a cero.")
            if oc_item.cantidad_recibida + cantidad > oc_item.cantidad:
                raise PurchaseError(
                    f"La cantidad recibida para {oc_item.producto.codigo} supera lo pedido "
                    f"({oc_item.cantidad_pendiente} pendiente)."
                )

            lote = None
            if data.get("numero_lote") and oc_item.producto.controla_lote:
                from apps.products.models import Lote

                lote, _ = Lote.objects.get_or_create(
                    producto=oc_item.producto,
                    numero_lote=data["numero_lote"],
                    defaults={"fecha_vencimiento": data.get("fecha_vencimiento")},
                )

            movimiento = InventoryService.registrar_entrada(
                producto=oc_item.producto,
                deposito=deposito,
                cantidad=cantidad,
                costo_unitario=oc_item.precio_unitario * (1 - oc_item.descuento_porcentaje / 100),
                moneda_costo_code=orden_compra.moneda.code,
                usuario=usuario,
                lote=lote,
                documento_tipo="RECEPCION_COMPRA",
                documento_referencia=recepcion.numero,
                fecha_valorizacion=timezone.now().date(),
            )

            RecepcionCompraItem.objects.create(
                recepcion=recepcion,
                orden_compra_item=oc_item,
                cantidad_recibida=cantidad,
                numero_lote=data.get("numero_lote", ""),
                fecha_vencimiento=data.get("fecha_vencimiento"),
                movimiento_inventario=movimiento,
            )

            oc_item.cantidad_recibida += cantidad
            oc_item.save(update_fields=["cantidad_recibida"])

        orden_compra.refresh_from_db()
        orden_compra.estado = (
            OrdenCompra.ESTADO_RECIBIDA_TOTAL if orden_compra.totalmente_recibida
            else OrdenCompra.ESTADO_RECIBIDA_PARCIAL
        )
        orden_compra.save(update_fields=["estado"])

        return recepcion

    @staticmethod
    def historial_proveedor(proveedor):
        """Historial simple de órdenes y facturas para comparación/seguimiento."""
        return {
            "ordenes_compra": list(
                proveedor.ordenes_compra.order_by("-fecha").values("numero", "estado", "fecha")[:50]
            ),
            "facturas": list(
                proveedor.facturas.order_by("-fecha_emision").values(
                    "numero_factura", "monto_total", "saldo_pendiente", "estado", "fecha_emision"
                )[:50]
            ),
        }
