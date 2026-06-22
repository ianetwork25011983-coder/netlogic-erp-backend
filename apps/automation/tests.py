from decimal import Decimal

import pytest

from apps.automation.models import Alerta, EjecucionRegla, ReglaAutomatizacion
from apps.automation.services import RuleEngineError, RuleEngineService
from apps.inventory.services import InventoryService


@pytest.mark.django_db
class TestEjemploStockBajoMinimo:
    """SI stock < mínimo ENTONCES generar solicitud de compra."""

    def test_genera_solicitud_de_compra_con_cantidad_sugerida(self, empresa, deposito, producto, user):
        from apps.purchases.models import SolicitudCompra

        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("5"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)

        ReglaAutomatizacion.objects.create(
            empresa=empresa, nombre="Stock bajo mínimo", tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PRODUCTO,
            condiciones=[{"campo": "stock_actual", "operador": "<", "campo_comparacion": "stock_minimo"}],
            accion=ReglaAutomatizacion.ACCION_GENERAR_SOLICITUD_COMPRA,
        )
        resultados = RuleEngineService.evaluar_producto(producto)
        assert resultados[0]["cumplida"] is True
        assert SolicitudCompra.objects.count() == 1
        item = SolicitudCompra.objects.first().items.first()
        assert item.producto == producto
        assert item.cantidad == Decimal("95")

    def test_no_genera_nada_si_el_stock_esta_por_encima_del_minimo(self, empresa, deposito, producto, user):
        from apps.purchases.models import SolicitudCompra

        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        ReglaAutomatizacion.objects.create(
            empresa=empresa, nombre="Stock bajo mínimo", tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PRODUCTO,
            condiciones=[{"campo": "stock_actual", "operador": "<", "campo_comparacion": "stock_minimo"}],
            accion=ReglaAutomatizacion.ACCION_GENERAR_SOLICITUD_COMPRA,
        )
        RuleEngineService.evaluar_producto(producto)
        assert SolicitudCompra.objects.count() == 0


@pytest.mark.django_db
class TestEjemploSinMovimiento:
    """SI producto sin movimiento > 180 días ENTONCES generar alerta."""

    def test_genera_alerta_para_producto_sin_ningun_movimiento(self, empresa, producto):
        regla = ReglaAutomatizacion.objects.create(
            empresa=empresa, nombre="Sin movimiento +180 días", tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PRODUCTO,
            condiciones=[{"campo": "dias_sin_movimiento", "operador": ">", "valor": 180}],
            accion=ReglaAutomatizacion.ACCION_GENERAR_ALERTA,
            parametros_accion={"mensaje": "Producto sin movimiento hace más de 180 días."},
        )
        RuleEngineService.evaluar_producto(producto)
        assert Alerta.objects.filter(regla=regla).count() == 1

    def test_no_genera_alerta_si_hay_movimiento_reciente(self, empresa, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        regla = ReglaAutomatizacion.objects.create(
            empresa=empresa, nombre="Sin movimiento +180 días", tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PRODUCTO,
            condiciones=[{"campo": "dias_sin_movimiento", "operador": ">", "valor": 180}],
            accion=ReglaAutomatizacion.ACCION_GENERAR_ALERTA,
        )
        RuleEngineService.evaluar_producto(producto)
        assert Alerta.objects.filter(regla=regla).count() == 0


@pytest.mark.django_db
class TestEjemploClienteVIP:
    """SI cliente VIP realiza pedido ENTONCES asignar prioridad."""

    def test_pedido_de_cliente_vip_recibe_prioridad_automaticamente(self, empresa, sucursal, lista_precio, deposito, producto, user, pyg):
        from apps.customers.models import Cliente
        from apps.orders.services import OrderService

        ReglaAutomatizacion.objects.create(
            empresa=empresa, nombre="Cliente VIP", tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PEDIDO_WEB,
            condiciones=[{"campo": "cliente_es_vip", "operador": "==", "valor": True}],
            accion=ReglaAutomatizacion.ACCION_ASIGNAR_PRIORIDAD, parametros_accion={"prioridad": "URGENTE"},
        )
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)

        cliente_vip = Cliente.objects.create(empresa=empresa, razon_social="VIP SA", ruc="80077777-3", moneda_default=pyg, es_vip=True)
        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente_vip, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("2")}],
        )
        pedido.refresh_from_db()
        assert pedido.prioridad == "URGENTE"

    def test_pedido_de_cliente_normal_mantiene_prioridad_normal(self, empresa, sucursal, cliente, lista_precio, deposito, producto, user):
        from apps.orders.services import OrderService

        ReglaAutomatizacion.objects.create(
            empresa=empresa, nombre="Cliente VIP", tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PEDIDO_WEB,
            condiciones=[{"campo": "cliente_es_vip", "operador": "==", "valor": True}],
            accion=ReglaAutomatizacion.ACCION_ASIGNAR_PRIORIDAD, parametros_accion={"prioridad": "URGENTE"},
        )
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)

        pedido = OrderService.crear_pedido(
            empresa=empresa, sucursal=sucursal, cliente=cliente, lista_precio=lista_precio,
            deposito_reserva=deposito, items_data=[{"producto_id": producto.id, "cantidad": Decimal("2")}],
        )
        pedido.refresh_from_db()
        assert pedido.prioridad == "NORMAL"


@pytest.mark.django_db
class TestBitacoraDeEjecucion:
    def test_se_registra_la_ejecucion_aunque_la_condicion_no_se_cumpla(self, empresa, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("50"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        regla = ReglaAutomatizacion.objects.create(
            empresa=empresa, nombre="Stock bajo mínimo", tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PRODUCTO,
            condiciones=[{"campo": "stock_actual", "operador": "<", "campo_comparacion": "stock_minimo"}],
            accion=ReglaAutomatizacion.ACCION_GENERAR_SOLICITUD_COMPRA,
        )
        RuleEngineService.evaluar_producto(producto)
        ejecucion = EjecucionRegla.objects.get(regla=regla)
        assert ejecucion.condicion_cumplida is False
        assert ejecucion.accion_ejecutada is False


@pytest.mark.django_db
class TestOperadorNoSoportado:
    def test_operador_invalido_lanza_excepcion(self, empresa, producto):
        regla = ReglaAutomatizacion(
            empresa=empresa, nombre="Regla inválida", tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PRODUCTO,
            condiciones=[{"campo": "stock_actual", "operador": "<>", "valor": 5}],
            accion=ReglaAutomatizacion.ACCION_GENERAR_ALERTA,
        )
        regla.save()
        with pytest.raises(RuleEngineError):
            RuleEngineService.evaluar_producto(producto)
