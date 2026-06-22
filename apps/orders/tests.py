from decimal import Decimal

import pytest

from apps.inventory.services import InventoryService
from apps.orders.models import PedidoWeb
from apps.orders.services import OrderError, OrderService
from apps.pricing.models import Cupon, PrecioProducto, Promocion
from apps.products.models import Categoria


@pytest.mark.django_db
class TestCrearPedido:
    def test_crear_pedido_valida_y_reserva_stock(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)

        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("5")}],
        )
        assert pedido.estado == PedidoWeb.ESTADO_VALIDADO
        disponible = InventoryService.cantidad_disponible_venta(producto, deposito)
        assert disponible == Decimal("45")

    def test_pedido_usa_precio_de_lista_y_aplica_promocion(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        import datetime

        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        PrecioProducto.objects.create(lista_precio=lista_precio, producto=producto, precio=Decimal("95000"))
        categoria = Categoria.objects.create(empresa=empresa, nombre="Electrónica")
        producto.categoria = categoria
        producto.save()
        Promocion.objects.create(
            empresa=empresa, nombre="Promo", descuento_porcentaje=Decimal("10"), categoria=categoria,
            vigencia_desde=datetime.date.today() - datetime.timedelta(days=1),
            vigencia_hasta=datetime.date.today() + datetime.timedelta(days=30),
        )

        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("5")}],
        )
        item = pedido.items.first()
        assert item.precio_unitario == Decimal("95000")
        assert item.descuento_porcentaje == Decimal("10")
        assert pedido.subtotal == Decimal("427500.00")

    def test_pedido_aplica_cupon_correctamente(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        import datetime

        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        Cupon.objects.create(
            empresa=empresa, codigo="BIENVENIDA", tipo_descuento=Cupon.TIPO_PORCENTAJE, valor=Decimal("5"),
            vigencia_desde=datetime.date.today(), vigencia_hasta=datetime.date.today() + datetime.timedelta(days=30),
        )
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("1")}],
            cupon_code="BIENVENIDA",
        )
        assert pedido.descuento_total == Decimal("5000.00")
        assert pedido.total == Decimal("95000.00")

    def test_pedido_con_stock_insuficiente_queda_rechazado_automaticamente(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("5"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("999")}],
        )
        assert pedido.estado == PedidoWeb.ESTADO_RECHAZADO
        assert pedido.motivo_rechazo != ""


@pytest.mark.django_db
class TestFlujoCompletoPedido:
    def test_flujo_completo_aprobar_picking_facturar_despachar_entregar(self, empresa, sucursal, punto_venta, cliente, lista_precio, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("5")}],
        )
        pedido = OrderService.aprobar_pedido(pedido, user)
        assert pedido.estado == PedidoWeb.ESTADO_APROBADO

        pedido = OrderService.marcar_en_picking(pedido, user)
        assert pedido.estado == PedidoWeb.ESTADO_EN_PICKING

        pedido = OrderService.facturar_pedido(pedido, punto_venta=punto_venta, usuario=user)
        assert pedido.estado == PedidoWeb.ESTADO_FACTURADO
        assert pedido.documento_venta is not None

        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.cantidad == Decimal("45")

        pedido = OrderService.marcar_despachado(pedido, user)
        assert pedido.estado == PedidoWeb.ESTADO_DESPACHADO

        pedido = OrderService.marcar_entregado(pedido, user)
        assert pedido.estado == PedidoWeb.ESTADO_ENTREGADO

        assert pedido.historial_estados.count() == 7

    def test_no_se_puede_aprobar_un_pedido_que_no_esta_validado(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("5"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("999")}],
        )
        assert pedido.estado == PedidoWeb.ESTADO_RECHAZADO
        with pytest.raises(OrderError):
            OrderService.aprobar_pedido(pedido, user)

    def test_cancelar_pedido_libera_la_reserva(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("10")}],
        )
        OrderService.cancelar_pedido(pedido, "Cliente cambió de opinión", user)
        disponible = InventoryService.cantidad_disponible_venta(producto, deposito)
        assert disponible == Decimal("50")

    def test_no_se_puede_cancelar_un_pedido_ya_facturado(self, empresa, sucursal, punto_venta, cliente, lista_precio, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("5")}],
        )
        pedido = OrderService.aprobar_pedido(pedido, user)
        pedido = OrderService.marcar_en_picking(pedido, user)
        pedido = OrderService.facturar_pedido(pedido, punto_venta=punto_venta, usuario=user)

        with pytest.raises(OrderError):
            OrderService.cancelar_pedido(pedido, "Demasiado tarde", user)
