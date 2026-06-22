from decimal import Decimal

import pytest

from apps.billing.models import DocumentoVenta
from apps.billing.services import BillingService
from apps.inventory.services import InventoryService
from apps.reports.pdf import generar_factura_pdf
from apps.reports.services import ReportService


@pytest.mark.django_db
class TestReportesExcel:
    def test_kardex_excel_incluye_header_y_movimientos(self, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)
        InventoryService.registrar_salida(producto=producto, deposito=deposito, cantidad=Decimal("3"), usuario=user)

        wb = ReportService.kardex_excel(producto, deposito=deposito)
        ws = wb.active
        assert ws.max_row == 3  # header + 2 movimientos
        assert ws.cell(row=1, column=1).value == "Fecha"

    def test_inventario_valorizado_excel_incluye_total_general(self, empresa, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("1000"), moneda_costo_code="PYG", usuario=user)

        wb = ReportService.inventario_valorizado_excel(empresa)
        ws = wb.active
        ultima_fila = [c.value for c in ws[ws.max_row]]
        assert "TOTAL GENERAL" in ultima_fila

    def test_ventas_excel_incluye_una_fila_por_documento(self, empresa, sucursal, punto_venta, cliente, producto, user):
        import datetime

        hoy = datetime.date.today()
        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("1000")}],
            usuario=user,
        )
        wb = ReportService.ventas_excel(empresa, hoy.replace(day=1), hoy)
        assert wb.active.max_row == 2

    def test_rentabilidad_excel_agrupa_por_producto(self, empresa, sucursal, punto_venta, cliente, producto, deposito, user):
        import datetime

        hoy = datetime.date.today()
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("2"), "precio_unitario": Decimal("100000")}],
            usuario=user, afecta_inventario=True, deposito_salida=deposito,
        )
        wb = ReportService.rentabilidad_excel(empresa, hoy.replace(day=1), hoy)
        ws = wb.active
        assert ws.max_row == 2
        fila = [c.value for c in ws[2]]
        assert fila[0] == producto.codigo


@pytest.mark.django_db
class TestFacturaPdf:
    def test_genera_pdf_valido(self, empresa, sucursal, punto_venta, cliente, producto, user):
        factura = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("100000")}],
            usuario=user,
        )
        pdf_bytes = generar_factura_pdf(factura)
        assert pdf_bytes[:4] == b"%PDF"
        assert len(pdf_bytes) > 1000
