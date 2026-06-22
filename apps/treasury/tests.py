from decimal import Decimal

import pytest

from apps.billing.models import DocumentoVenta
from apps.billing.services import BillingService
from apps.purchases.models import FacturaProveedor
from apps.treasury.models import Caja
from apps.treasury.services import TreasuryError, TreasuryService


@pytest.fixture
def caja(db, empresa, sucursal):
    return Caja.objects.create(empresa=empresa, sucursal=sucursal, codigo="C01", nombre="Caja Principal")


@pytest.mark.django_db
class TestAperturaCierreCaja:
    def test_abrir_caja_crea_apertura(self, caja, user, pyg):
        apertura = TreasuryService.abrir_caja(caja, user, Decimal("500000"), pyg)
        assert apertura.estado == "ABIERTA"

    def test_no_se_puede_abrir_dos_veces_sin_cerrar(self, caja, user, pyg):
        TreasuryService.abrir_caja(caja, user, Decimal("500000"), pyg)
        with pytest.raises(TreasuryError):
            TreasuryService.abrir_caja(caja, user, Decimal("100000"), pyg)

    def test_cierre_calcula_diferencia_correctamente(self, caja, user, pyg):
        apertura = TreasuryService.abrir_caja(caja, user, Decimal("500000"), pyg)
        TreasuryService.registrar_movimiento(
            apertura, tipo="INGRESO", concepto="OTRO", medio_pago="EFECTIVO", monto=Decimal("100000"), moneda=pyg, usuario=user,
        )
        TreasuryService.registrar_movimiento(
            apertura, tipo="EGRESO", concepto="GASTO", medio_pago="EFECTIVO", monto=Decimal("20000"), moneda=pyg, usuario=user,
        )
        cierre = TreasuryService.cerrar_caja(apertura, Decimal("575000"), user)
        assert cierre.monto_esperado_efectivo == Decimal("580000")
        assert cierre.diferencia == Decimal("-5000")

        apertura.refresh_from_db()
        assert apertura.estado == "CERRADA"

    def test_no_se_pueden_registrar_movimientos_en_caja_cerrada(self, caja, user, pyg):
        apertura = TreasuryService.abrir_caja(caja, user, Decimal("500000"), pyg)
        TreasuryService.cerrar_caja(apertura, Decimal("500000"), user)
        with pytest.raises(TreasuryError):
            TreasuryService.registrar_movimiento(
                apertura, tipo="INGRESO", concepto="OTRO", medio_pago="EFECTIVO", monto=Decimal("1000"), moneda=pyg, usuario=user,
            )


@pytest.mark.django_db
class TestCobroFactura:
    def test_cobro_parcial_actualiza_saldo_pendiente(self, caja, user, pyg, empresa, sucursal, punto_venta, cliente, producto):
        apertura = TreasuryService.abrir_caja(caja, user, Decimal("0"), pyg)
        factura = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("2"), "precio_unitario": Decimal("100000")}],
            usuario=user, condicion_venta="CREDITO",
        )
        assert factura.saldo_pendiente == Decimal("200000.00")

        TreasuryService.registrar_cobro_factura(apertura, factura, Decimal("100000"), "EFECTIVO", user)
        factura.refresh_from_db()
        assert factura.saldo_pendiente == Decimal("100000.00")

    def test_no_se_puede_cobrar_mas_del_saldo_pendiente(self, caja, user, pyg, empresa, sucursal, punto_venta, cliente, producto):
        apertura = TreasuryService.abrir_caja(caja, user, Decimal("0"), pyg)
        factura = BillingService.emitir_documento(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=DocumentoVenta.TIPO_FACTURA,
            cliente=cliente, moneda_code="PYG", items_data=[{"producto_id": producto.id, "cantidad": Decimal("1"), "precio_unitario": Decimal("100000")}],
            usuario=user, condicion_venta="CREDITO",
        )
        with pytest.raises(TreasuryError):
            TreasuryService.registrar_cobro_factura(apertura, factura, Decimal("999999"), "EFECTIVO", user)


@pytest.mark.django_db
class TestPagoProveedor:
    def test_pago_total_marca_factura_como_pagada(self, caja, user, pyg, empresa, proveedor):
        from datetime import date

        apertura = TreasuryService.abrir_caja(caja, user, Decimal("0"), pyg)
        factura_prov = FacturaProveedor.objects.create(
            empresa=empresa, proveedor=proveedor, numero_factura="001-001-555", moneda=pyg,
            monto_total=Decimal("300000"), saldo_pendiente=Decimal("300000"), fecha_emision=date.today(),
        )
        TreasuryService.registrar_pago_proveedor(apertura, factura_prov, Decimal("300000"), "TRANSFERENCIA", user)
        factura_prov.refresh_from_db()
        assert factura_prov.estado == FacturaProveedor.ESTADO_PAGADA
        assert factura_prov.saldo_pendiente == Decimal("0.00")

    def test_pago_parcial_marca_pagada_parcial(self, caja, user, pyg, empresa, proveedor):
        from datetime import date

        apertura = TreasuryService.abrir_caja(caja, user, Decimal("0"), pyg)
        factura_prov = FacturaProveedor.objects.create(
            empresa=empresa, proveedor=proveedor, numero_factura="001-001-556", moneda=pyg,
            monto_total=Decimal("300000"), saldo_pendiente=Decimal("300000"), fecha_emision=date.today(),
        )
        TreasuryService.registrar_pago_proveedor(apertura, factura_prov, Decimal("100000"), "TRANSFERENCIA", user)
        factura_prov.refresh_from_db()
        assert factura_prov.estado == FacturaProveedor.ESTADO_PAGADA_PARCIAL


@pytest.mark.django_db
class TestMovimientoBancario:
    def test_deposito_incrementa_saldo(self, empresa, pyg, user):
        from apps.treasury.models import Banco, CuentaBancaria

        banco = Banco.objects.create(nombre="Banco Test")
        cuenta = CuentaBancaria.objects.create(empresa=empresa, banco=banco, numero_cuenta="123456", moneda=pyg, saldo_actual=Decimal("0"))

        TreasuryService.registrar_movimiento_bancario(cuenta, tipo="DEPOSITO", monto=Decimal("500000"), usuario=user)
        cuenta.refresh_from_db()
        assert cuenta.saldo_actual == Decimal("500000")

    def test_retiro_sin_saldo_suficiente_falla(self, empresa, pyg, user):
        from apps.treasury.models import Banco, CuentaBancaria

        banco = Banco.objects.create(nombre="Banco Test")
        cuenta = CuentaBancaria.objects.create(empresa=empresa, banco=banco, numero_cuenta="123457", moneda=pyg, saldo_actual=Decimal("1000"))

        with pytest.raises(TreasuryError):
            TreasuryService.registrar_movimiento_bancario(cuenta, tipo="RETIRO", monto=Decimal("999999"), usuario=user)
