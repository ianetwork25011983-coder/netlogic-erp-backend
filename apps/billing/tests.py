from decimal import Decimal

import pytest

from apps.billing.models import DocumentoVenta
from apps.billing.services import BillingError, BillingService
from apps.inventory.services import InventoryService


@pytest.mark.django_db
class TestEmitirFactura:
    def test_factura_calcula_subtotal_impuesto_y_total(self, empresa, sucursal, punto_venta, cliente, producto, deposito, user, impuesto_iva10):
        producto.impuesto = impuesto_iva10
        producto.save()
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)

        factura = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG",
            items_data=[{"producto_id": producto.id, "cantidad": Decimal("3"), "precio_unitario": Decimal("100000")}],
            usuario=user, afecta_inventario=True, deposito_salida=deposito,
        )
        assert factura.subtotal == Decimal("300000.00")
        assert factura.impuesto_total == Decimal("30000.00")
        assert factura.total == Decimal("330000.00")
        assert factura.estado == DocumentoVenta.ESTADO_EMITIDA

    def test_factura_descuenta_stock_real(self, empresa, sucursal, punto_venta, cliente, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)

        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG",
            items_data=[{"producto_id": producto.id, "cantidad": Decimal("3"), "precio_unitario": Decimal("100000")}],
            usuario=user, afecta_inventario=True, deposito_salida=deposito,
        )
        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.cantidad == Decimal("7")

    def test_factura_con_stock_insuficiente_no_se_emite_y_no_modifica_stock(self, empresa, sucursal, punto_venta, cliente, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("5"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)

        with pytest.raises(BillingError):
            BillingService.emitir_documento(
                empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
                cliente=cliente, moneda_code="PYG",
                items_data=[{"producto_id": producto.id, "cantidad": Decimal("999"), "precio_unitario": Decimal("100000")}],
                usuario=user, afecta_inventario=True, deposito_salida=deposito,
            )
        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.cantidad == Decimal("5")

    def test_numeracion_correlativa_por_punto_venta_y_tipo(self, empresa, sucursal, punto_venta, cliente, producto, user):
        f1 = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("1000")}],
            usuario=user,
        )
        f2 = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("1000")}],
            usuario=user,
        )
        assert f1.numero == "001-001-0000001"
        assert f2.numero == "001-001-0000002"

    def test_nota_credito_debito_requiere_documento_referencia(self, empresa, sucursal, punto_venta, cliente, producto, user):
        with pytest.raises(BillingError):
            BillingService.emitir_documento(
                empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_NOTA_CREDITO,
                cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("1000")}],
                usuario=user,
            )


@pytest.mark.django_db
class TestNotaCredito:
    def test_nota_credito_repone_stock(self, empresa, sucursal, punto_venta, cliente, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        factura = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("3"), "precio_unitario": Decimal("100000")}],
            usuario=user, afecta_inventario=True, deposito_salida=deposito,
        )
        BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_NOTA_CREDITO,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("100000")}],
            usuario=user, afecta_inventario=True, deposito_salida=deposito, documento_referencia=factura,
        )
        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.cantidad == Decimal("8")


@pytest.mark.django_db
class TestAnulacion:
    def test_anular_factura_repone_stock(self, empresa, sucursal, punto_venta, cliente, producto, deposito, user):
        InventoryService.registrar_entrada(producto=producto, deposito=deposito, cantidad=Decimal("10"), costo_unitario=Decimal("60000"), moneda_costo_code="PYG", usuario=user)
        factura = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("3"), "precio_unitario": Decimal("100000")}],
            usuario=user, afecta_inventario=True, deposito_salida=deposito,
        )
        BillingService.anular_documento(factura, "Cliente canceló", user)

        factura.refresh_from_db()
        assert factura.estado == DocumentoVenta.ESTADO_ANULADA
        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.cantidad == Decimal("10")

    def test_no_se_puede_anular_dos_veces(self, empresa, sucursal, punto_venta, cliente, producto, user):
        factura = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("1000")}],
            usuario=user,
        )
        BillingService.anular_documento(factura, "Motivo 1", user)
        with pytest.raises(BillingError):
            BillingService.anular_documento(factura, "Motivo 2", user)


@pytest.mark.django_db
class TestDescuentoGlobal:
    def test_descuento_global_se_resta_del_total(self, empresa, sucursal, punto_venta, cliente, producto, user):
        factura = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG",
            items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("100000")}],
            usuario=user, descuento_global=Decimal("10000"),
        )
        assert factura.subtotal == Decimal("100000.00")
        assert factura.descuento_global == Decimal("10000.00")
        assert factura.total == Decimal("90000.00")

    def test_descuento_global_no_puede_superar_el_total(self, empresa, sucursal, punto_venta, cliente, producto, user):
        with pytest.raises(BillingError):
            BillingService.emitir_documento(
                empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
                cliente=cliente, moneda_code="PYG",
                items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("1000")}],
                usuario=user, descuento_global=Decimal("999999"),
            )


@pytest.mark.django_db
class TestConvertirPresupuesto:
    def test_convertir_presupuesto_genera_factura_referenciada(self, empresa, sucursal, punto_venta, cliente, producto, user):
        presupuesto = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_PRESUPUESTO,
            cliente=cliente, moneda_code="PYG",
            items_data=[{"producto_id": producto.id, "cantidad": Decimal("2"), "precio_unitario": Decimal("100000")}],
            usuario=user, afecta_inventario=False,
        )
        factura = BillingService.convertir_presupuesto_a_factura(presupuesto, punto_venta=punto_venta, usuario=user, afecta_inventario=False)

        assert factura.tipo_documento == DocumentoVenta.TIPO_FACTURA
        assert factura.documento_referencia == presupuesto
        assert factura.total == presupuesto.total
