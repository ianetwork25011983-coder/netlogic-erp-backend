import datetime
from decimal import Decimal

import pytest

from apps.analytics.services import DashboardService
from apps.billing.models import DocumentoVenta
from apps.billing.services import BillingService
from apps.inventory.services import InventoryService


@pytest.mark.django_db
class TestVentasResumen:
    def test_ventas_resumen_calcula_total_y_ticket_promedio(self, empresa, sucursal, punto_venta, cliente, producto, user):
        hoy = datetime.date.today()
        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("100000")}],
            usuario=user,
        )
        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("2"), "precio_unitario": Decimal("100000")}],
            usuario=user,
        )
        resumen = DashboardService.ventas_resumen(empresa, hoy.replace(day=1), hoy)
        assert resumen["cantidad_facturas"] == 2
        assert resumen["total_ventas_pyg"] == Decimal("300000.00")
        assert resumen["ticket_promedio_pyg"] == Decimal("150000.00")


@pytest.mark.django_db
class TestRentabilidad:
    def test_rentabilidad_calcula_margen_correctamente(self, empresa, sucursal, punto_venta, cliente, producto, deposito, user):
        hoy = datetime.date.today()
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("5"), "precio_unitario": Decimal("100000")}],
            usuario=user, afecta_inventario=True, deposito_salida=deposito,
        )
        resultado = DashboardService.rentabilidad(empresa, hoy.replace(day=1), hoy)
        assert resultado["ventas_netas_pyg"] == Decimal("500000")
        assert resultado["costo_ventas_pyg"] == Decimal("300000")
        assert resultado["margen_bruto_pyg"] == Decimal("200000")
        assert resultado["margen_porcentaje"] == Decimal("40")


@pytest.mark.django_db
class TestInventarioResumen:
    def test_detecta_productos_bajo_stock_minimo(self, empresa, deposito, producto, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("5"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        resumen = DashboardService.inventario_resumen(empresa)
        assert resumen["productos_bajo_stock_minimo"] == 1


@pytest.mark.django_db
class TestComparativoPeriodo:
    def test_comparativo_sin_ventas_anteriores_devuelve_variacion_none(self, empresa):
        hoy = datetime.date.today()
        resultado = DashboardService.comparativo_periodo(empresa, hoy.replace(day=1), hoy)
        assert resultado["variacion_porcentaje"] is None
