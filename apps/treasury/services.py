"""
Servicio de Tesorería (Módulo 11).

`registrar_cobro_factura` y `registrar_pago_proveedor` son los ÚNICOS
puntos que deben actualizar `DocumentoVenta.saldo_pendiente` /
`FacturaProveedor.saldo_pendiente`; el resto del ERP no debe tocar esos
campos directamente.
"""
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from .models import AperturaCaja, CierreCaja, MovimientoBancario, MovimientoCaja


class TreasuryError(Exception):
    pass


class TreasuryService:
    @staticmethod
    @transaction.atomic
    def abrir_caja(caja, usuario, monto_inicial, moneda, observaciones=""):
        if AperturaCaja.objects.filter(caja=caja, estado=AperturaCaja.ESTADO_ABIERTA).exists():
            raise TreasuryError(f"La caja {caja} ya tiene una apertura activa sin cerrar.")

        return AperturaCaja.objects.create(
            caja=caja, usuario=usuario, monto_inicial=monto_inicial, moneda=moneda, observaciones=observaciones,
        )

    @staticmethod
    def _saldo_esperado_efectivo(apertura_caja):
        ingresos = apertura_caja.movimientos.filter(
            tipo=MovimientoCaja.TIPO_INGRESO, medio_pago=MovimientoCaja.MEDIO_EFECTIVO
        ).aggregate(total=Sum("monto"))["total"] or Decimal("0")
        egresos = apertura_caja.movimientos.filter(
            tipo=MovimientoCaja.TIPO_EGRESO, medio_pago=MovimientoCaja.MEDIO_EFECTIVO
        ).aggregate(total=Sum("monto"))["total"] or Decimal("0")
        return apertura_caja.monto_inicial + ingresos - egresos

    @classmethod
    @transaction.atomic
    def cerrar_caja(cls, apertura_caja, monto_contado_efectivo, usuario, observaciones=""):
        if apertura_caja.estado != AperturaCaja.ESTADO_ABIERTA:
            raise TreasuryError("Esta apertura de caja ya está cerrada.")

        monto_esperado = cls._saldo_esperado_efectivo(apertura_caja)
        diferencia = Decimal(monto_contado_efectivo) - monto_esperado

        cierre = CierreCaja.objects.create(
            apertura_caja=apertura_caja, monto_contado_efectivo=monto_contado_efectivo,
            monto_esperado_efectivo=monto_esperado, diferencia=diferencia, usuario=usuario,
            observaciones=observaciones,
        )
        apertura_caja.estado = AperturaCaja.ESTADO_CERRADA
        apertura_caja.save(update_fields=["estado"])
        return cierre

    @staticmethod
    def registrar_movimiento(
        apertura_caja, *, tipo, concepto, medio_pago, monto, moneda, usuario,
        referencia_tipo="", referencia_id="", observaciones="",
    ):
        if apertura_caja.estado != AperturaCaja.ESTADO_ABIERTA:
            raise TreasuryError("No se pueden registrar movimientos en una caja cerrada.")

        return MovimientoCaja.objects.create(
            apertura_caja=apertura_caja, tipo=tipo, concepto=concepto, medio_pago=medio_pago,
            monto=monto, moneda=moneda, usuario=usuario, referencia_tipo=referencia_tipo,
            referencia_id=str(referencia_id) if referencia_id else "", observaciones=observaciones,
        )

    @classmethod
    @transaction.atomic
    def registrar_cobro_factura(cls, apertura_caja, documento_venta, monto, medio_pago, usuario, observaciones=""):
        monto = Decimal(monto)
        if monto > documento_venta.saldo_pendiente:
            raise TreasuryError(
                f"El monto a cobrar ({monto}) supera el saldo pendiente de la factura ({documento_venta.saldo_pendiente})."
            )

        movimiento = cls.registrar_movimiento(
            apertura_caja, tipo=MovimientoCaja.TIPO_INGRESO, concepto=MovimientoCaja.CONCEPTO_COBRO_FACTURA,
            medio_pago=medio_pago, monto=monto, moneda=documento_venta.moneda, usuario=usuario,
            referencia_tipo="DOCUMENTO_VENTA", referencia_id=documento_venta.id, observaciones=observaciones,
        )

        documento_venta.saldo_pendiente -= monto
        documento_venta.save(update_fields=["saldo_pendiente"])

        return movimiento

    @classmethod
    @transaction.atomic
    def registrar_pago_proveedor(cls, apertura_caja, factura_proveedor, monto, medio_pago, usuario, observaciones=""):
        from apps.purchases.models import FacturaProveedor

        monto = Decimal(monto)
        if monto > factura_proveedor.saldo_pendiente:
            raise TreasuryError(
                f"El monto a pagar ({monto}) supera el saldo pendiente de la factura ({factura_proveedor.saldo_pendiente})."
            )

        movimiento = cls.registrar_movimiento(
            apertura_caja, tipo=MovimientoCaja.TIPO_EGRESO, concepto=MovimientoCaja.CONCEPTO_PAGO_PROVEEDOR,
            medio_pago=medio_pago, monto=monto, moneda=factura_proveedor.moneda, usuario=usuario,
            referencia_tipo="FACTURA_PROVEEDOR", referencia_id=factura_proveedor.id, observaciones=observaciones,
        )

        factura_proveedor.saldo_pendiente -= monto
        if factura_proveedor.saldo_pendiente <= 0:
            factura_proveedor.estado = FacturaProveedor.ESTADO_PAGADA
        else:
            factura_proveedor.estado = FacturaProveedor.ESTADO_PAGADA_PARCIAL
        factura_proveedor.save(update_fields=["saldo_pendiente", "estado"])

        return movimiento

    @staticmethod
    @transaction.atomic
    def registrar_movimiento_bancario(cuenta_bancaria, *, tipo, monto, usuario, referencia="", observaciones=""):
        monto = Decimal(monto)
        if tipo in (MovimientoBancario.TIPO_DEPOSITO, MovimientoBancario.TIPO_TRANSFERENCIA_ENTRADA):
            cuenta_bancaria.saldo_actual += monto
        else:
            if monto > cuenta_bancaria.saldo_actual:
                raise TreasuryError("La cuenta no tiene saldo suficiente para este movimiento.")
            cuenta_bancaria.saldo_actual -= monto
        cuenta_bancaria.save(update_fields=["saldo_actual"])

        return MovimientoBancario.objects.create(
            cuenta_bancaria=cuenta_bancaria, tipo=tipo, monto=monto, saldo_posterior=cuenta_bancaria.saldo_actual,
            referencia=referencia, observaciones=observaciones, usuario=usuario,
        )
