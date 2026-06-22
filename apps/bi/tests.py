import datetime
from decimal import Decimal

import pytest

from apps.bi.services import BIService
from apps.billing.models import DocumentoVenta
from apps.billing.services import BillingService


@pytest.mark.django_db
class TestAbcProductos:
    def test_clasifica_productos_segun_pareto(self, empresa, sucursal, punto_venta, cliente, producto, user, unidad_medida, pyg):
        from apps.products.models import Producto

        producto_b = Producto.objects.create(
            empresa=empresa, tipo=Producto.TIPO_PRODUCTO, codigo="P-002", nombre="Producto secundario",
            unidad_medida=unidad_medida, moneda_costo=pyg, moneda_precio=pyg,
        )
        hoy = datetime.date.today()
        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("10"), "precio_unitario": Decimal("100000")}],
            usuario=user,
        )
        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto_b.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("1000")}],
            usuario=user,
        )
        resultado = BIService.abc_productos(empresa, hoy.replace(day=1), hoy)
        principal = next(r for r in resultado if r["codigo"] == producto.codigo)
        assert principal["clase_abc"] == "A"


@pytest.mark.django_db
class TestClientesEnDeclive:
    def test_detecta_caida_de_compras_respecto_al_periodo_anterior(self, empresa, sucursal, punto_venta, cliente, producto, user):
        import calendar

        hoy = datetime.date.today()
        mes_pasado = hoy.month - 1 or 12
        anio_mes_pasado = hoy.year if hoy.month > 1 else hoy.year - 1
        fecha_mes_pasado = datetime.date(anio_mes_pasado, mes_pasado, min(hoy.day, calendar.monthrange(anio_mes_pasado, mes_pasado)[1]))

        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("10"), "precio_unitario": Decimal("100000")}],
            usuario=user, fecha_emision=fecha_mes_pasado,
        )

        resultado = BIService.clientes_en_declive(empresa, hoy.replace(day=1), hoy, umbral_caida_porcentaje=20)
        assert len(resultado) == 1
        assert float(resultado[0]["variacion_porcentaje"]) == -100.0

    def test_sin_compras_anteriores_no_hay_declive_a_detectar(self, empresa):
        hoy = datetime.date.today()
        resultado = BIService.clientes_en_declive(empresa, hoy.replace(day=1), hoy)
        assert resultado == []
