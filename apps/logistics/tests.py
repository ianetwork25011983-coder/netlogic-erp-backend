from decimal import Decimal

import pytest

from apps.inventory.services import InventoryService
from apps.logistics.models import OrdenPicking, Transportista
from apps.logistics.services import LogisticsError, LogisticsService
from apps.orders.models import PedidoWeb
from apps.orders.services import OrderService


@pytest.fixture
def transportista(db, empresa):
    return Transportista.objects.create(empresa=empresa, razon_social="Transportes Rápidos SA", tipo=Transportista.TIPO_TERCERIZADO)


@pytest.mark.django_db
class TestPickingYPacking:
    def test_iniciar_picking_requiere_pedido_en_picking(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("5")}],
        )
        with pytest.raises(LogisticsError):
            LogisticsService.iniciar_picking(pedido, deposito, usuario_asignado=user)

    def test_flujo_picking_packing_completo(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("5")}],
        )
        pedido = OrderService.aprobar_pedido(pedido, user)
        pedido = OrderService.marcar_en_picking(pedido, user)

        orden_picking = LogisticsService.iniciar_picking(pedido, deposito, usuario_asignado=user)
        assert orden_picking.estado == OrdenPicking.ESTADO_EN_PROCESO

        item = pedido.items.first()
        orden_picking = LogisticsService.completar_picking(
            orden_picking, [{"pedido_web_item_id": item.id, "cantidad_pickeada": item.cantidad}], user
        )
        assert orden_picking.estado == OrdenPicking.ESTADO_COMPLETADO

        packing = LogisticsService.crear_packing(orden_picking, cantidad_bultos=1, peso_total_kg=Decimal("2.5"), usuario=user)
        assert packing.cantidad_bultos == 1

    def test_no_se_puede_armar_packing_sin_picking_completado(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("5")}],
        )
        pedido = OrderService.aprobar_pedido(pedido, user)
        pedido = OrderService.marcar_en_picking(pedido, user)
        orden_picking = LogisticsService.iniciar_picking(pedido, deposito, usuario_asignado=user)

        with pytest.raises(LogisticsError):
            LogisticsService.crear_packing(orden_picking, cantidad_bultos=1, usuario=user)


@pytest.mark.django_db
class TestDespachoYEntrega:
    def test_crear_despacho_marca_pedido_despachado(self, empresa, sucursal, punto_venta, cliente, lista_precio, deposito, producto, user, transportista):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("5")}],
        )
        pedido = OrderService.aprobar_pedido(pedido, user)
        pedido = OrderService.marcar_en_picking(pedido, user)
        pedido = OrderService.facturar_pedido(pedido, punto_venta=punto_venta, usuario=user)

        despacho = LogisticsService.crear_despacho(empresa, [pedido.documento_venta], transportista, user, conductor_nombre="Carlos Gómez")
        assert despacho.estado == "EN_RUTA"

        pedido.refresh_from_db()
        assert pedido.estado == PedidoWeb.ESTADO_DESPACHADO

    def test_registrar_entrega_marca_pedido_y_despacho_entregados(self, empresa, sucursal, punto_venta, cliente, lista_precio, deposito, producto, user, transportista):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("5")}],
        )
        pedido = OrderService.aprobar_pedido(pedido, user)
        pedido = OrderService.marcar_en_picking(pedido, user)
        pedido = OrderService.facturar_pedido(pedido, punto_venta=punto_venta, usuario=user)
        despacho = LogisticsService.crear_despacho(empresa, [pedido.documento_venta], transportista, user)

        despacho_doc = despacho.documentos.first()
        LogisticsService.registrar_entrega(despacho_doc, estado_entrega="ENTREGADO", usuario=user, firma_recibido="Ana Pérez")

        despacho.refresh_from_db()
        pedido.refresh_from_db()
        assert despacho.estado == "ENTREGADO"
        assert pedido.estado == PedidoWeb.ESTADO_ENTREGADO
