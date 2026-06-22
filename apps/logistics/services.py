"""
Servicio de Logística (Módulo 12).

Las transiciones de `PedidoWeb.estado` siguen siendo responsabilidad de
`OrderService` (Módulo 8); este servicio las dispara cuando completa el
picking o registra una entrega, para que no haya dos máquinas de estado
independientes para el mismo pedido.
"""
from django.db import transaction
from django.utils import timezone

from .models import Despacho, DespachoDocumento, OrdenPacking, OrdenPicking, OrdenPickingItem


class LogisticsError(Exception):
    pass


class LogisticsService:
    @staticmethod
    def _siguiente_numero_despacho(empresa):
        ultimo = Despacho.objects.filter(empresa=empresa).order_by("-id").first()
        siguiente = (ultimo.id + 1) if ultimo else 1
        return f"DESP-{empresa.id:03d}-{siguiente:06d}"

    @staticmethod
    @transaction.atomic
    def iniciar_picking(pedido_web, deposito, usuario_asignado=None):
        from apps.orders.models import PedidoWeb

        if pedido_web.estado != PedidoWeb.ESTADO_EN_PICKING:
            raise LogisticsError(
                f"El pedido debe estar en estado EN_PICKING para iniciar el picking (estado actual: {pedido_web.estado})."
            )
        if hasattr(pedido_web, "orden_picking"):
            raise LogisticsError("Este pedido ya tiene una orden de picking.")

        return OrdenPicking.objects.create(
            pedido_web=pedido_web, deposito=deposito, usuario_asignado=usuario_asignado,
            estado=OrdenPicking.ESTADO_EN_PROCESO, fecha_inicio=timezone.now(),
        )

    @staticmethod
    @transaction.atomic
    def completar_picking(orden_picking, items_pickeados, usuario):
        """`items_pickeados`: lista de dicts {"pedido_web_item_id", "cantidad_pickeada", "ubicacion_id" opcional}."""
        if orden_picking.estado == OrdenPicking.ESTADO_COMPLETADO:
            raise LogisticsError("Esta orden de picking ya fue completada.")

        for item_data in items_pickeados:
            OrdenPickingItem.objects.create(
                orden_picking=orden_picking,
                pedido_web_item_id=item_data["pedido_web_item_id"],
                cantidad_pickeada=item_data["cantidad_pickeada"],
                ubicacion_id=item_data.get("ubicacion_id"),
            )

        orden_picking.estado = OrdenPicking.ESTADO_COMPLETADO
        orden_picking.fecha_fin = timezone.now()
        orden_picking.save(update_fields=["estado", "fecha_fin"])
        return orden_picking

    @staticmethod
    def crear_packing(orden_picking, *, cantidad_bultos=1, peso_total_kg=None, volumen_total_m3=None, usuario=None):
        if orden_picking.estado != OrdenPicking.ESTADO_COMPLETADO:
            raise LogisticsError("El picking debe estar COMPLETADO antes de armar el packing.")

        return OrdenPacking.objects.create(
            orden_picking=orden_picking, cantidad_bultos=cantidad_bultos,
            peso_total_kg=peso_total_kg, volumen_total_m3=volumen_total_m3, usuario=usuario,
        )

    @classmethod
    @transaction.atomic
    def crear_despacho(
        cls, empresa, documentos_venta, transportista, usuario,
        vehiculo=None, ruta=None, conductor_nombre="", observaciones="",
    ):
        from apps.orders.services import OrderService

        despacho = Despacho.objects.create(
            empresa=empresa, numero=cls._siguiente_numero_despacho(empresa), transportista=transportista,
            vehiculo=vehiculo, ruta=ruta, conductor_nombre=conductor_nombre, usuario=usuario,
            observaciones=observaciones,
        )

        for orden, documento in enumerate(documentos_venta, start=1):
            DespachoDocumento.objects.create(
                despacho=despacho, documento_venta=documento, orden_entrega=orden,
                direccion_entrega=documento.cliente.direccion,
            )
            pedido = documento.pedido_origen.first()
            if pedido:
                try:
                    OrderService.marcar_despachado(pedido, usuario)
                except Exception:
                    pass  # el pedido puede no estar en estado FACTURADO; no bloquea el despacho físico

        despacho.estado = Despacho.ESTADO_EN_RUTA
        despacho.save(update_fields=["estado"])
        return despacho

    @classmethod
    @transaction.atomic
    def registrar_entrega(cls, despacho_documento, *, estado_entrega, usuario, firma_recibido="", observaciones=""):
        from apps.orders.services import OrderService

        despacho_documento.estado_entrega = estado_entrega
        despacho_documento.fecha_entrega_real = timezone.now()
        despacho_documento.firma_recibido = firma_recibido
        despacho_documento.observaciones = observaciones
        despacho_documento.save(update_fields=["estado_entrega", "fecha_entrega_real", "firma_recibido", "observaciones"])

        despacho = despacho_documento.despacho
        estados = list(despacho.documentos.values_list("estado_entrega", flat=True))
        if all(e == DespachoDocumento.ESTADO_ENTREGADO for e in estados):
            despacho.estado = Despacho.ESTADO_ENTREGADO
        elif any(e == DespachoDocumento.ESTADO_ENTREGADO for e in estados):
            despacho.estado = Despacho.ESTADO_PARCIAL
        despacho.save(update_fields=["estado"])

        if estado_entrega == DespachoDocumento.ESTADO_ENTREGADO:
            documento = despacho_documento.documento_venta
            pedido = documento.pedido_origen.first()
            if pedido:
                try:
                    OrderService.marcar_entregado(pedido, usuario)
                except Exception:
                    pass

        return despacho_documento
