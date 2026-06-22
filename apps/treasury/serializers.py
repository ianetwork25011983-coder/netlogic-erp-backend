from rest_framework import serializers

from .models import AperturaCaja, Banco, Caja, CierreCaja, CuentaBancaria, MovimientoBancario, MovimientoCaja


class CajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Caja
        fields = ["id", "empresa", "sucursal", "punto_venta", "codigo", "nombre", "active"]


class MovimientoCajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoCaja
        fields = [
            "id", "apertura_caja", "tipo", "concepto", "medio_pago", "monto", "moneda",
            "referencia_tipo", "referencia_id", "usuario", "observaciones", "fecha",
        ]
        read_only_fields = fields


class AperturaCajaSerializer(serializers.ModelSerializer):
    movimientos = MovimientoCajaSerializer(many=True, read_only=True)
    saldo_esperado_efectivo = serializers.SerializerMethodField()

    class Meta:
        model = AperturaCaja
        fields = [
            "id", "caja", "usuario", "monto_inicial", "moneda", "estado",
            "observaciones", "fecha_apertura", "movimientos", "saldo_esperado_efectivo",
        ]
        read_only_fields = ["estado", "fecha_apertura"]

    def get_saldo_esperado_efectivo(self, obj):
        from .services import TreasuryService

        return TreasuryService._saldo_esperado_efectivo(obj)


class CierreCajaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CierreCaja
        fields = [
            "id", "apertura_caja", "monto_contado_efectivo", "monto_esperado_efectivo",
            "diferencia", "usuario", "observaciones", "fecha_cierre",
        ]
        read_only_fields = fields


class BancoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Banco
        fields = ["id", "nombre", "active"]


class CuentaBancariaSerializer(serializers.ModelSerializer):
    class Meta:
        model = CuentaBancaria
        fields = ["id", "empresa", "banco", "numero_cuenta", "tipo_cuenta", "moneda", "saldo_actual", "active"]
        read_only_fields = ["saldo_actual"]


class MovimientoBancarioSerializer(serializers.ModelSerializer):
    class Meta:
        model = MovimientoBancario
        fields = [
            "id", "cuenta_bancaria", "tipo", "monto", "saldo_posterior",
            "referencia", "observaciones", "usuario", "fecha",
        ]
        read_only_fields = fields


# --- Inputs de acción ---

class AbrirCajaInputSerializer(serializers.Serializer):
    caja_id = serializers.IntegerField()
    monto_inicial = serializers.DecimalField(max_digits=18, decimal_places=2)
    moneda_id = serializers.IntegerField()
    observaciones = serializers.CharField(required=False, allow_blank=True)


class CerrarCajaInputSerializer(serializers.Serializer):
    monto_contado_efectivo = serializers.DecimalField(max_digits=18, decimal_places=2)
    observaciones = serializers.CharField(required=False, allow_blank=True)


class RegistrarMovimientoInputSerializer(serializers.Serializer):
    apertura_caja_id = serializers.IntegerField()
    tipo = serializers.ChoiceField(choices=MovimientoCaja.TIPO_CHOICES)
    concepto = serializers.ChoiceField(choices=MovimientoCaja.CONCEPTO_CHOICES)
    medio_pago = serializers.ChoiceField(choices=MovimientoCaja.MEDIO_CHOICES)
    monto = serializers.DecimalField(max_digits=18, decimal_places=2)
    moneda_id = serializers.IntegerField()
    observaciones = serializers.CharField(required=False, allow_blank=True)


class CobroFacturaInputSerializer(serializers.Serializer):
    apertura_caja_id = serializers.IntegerField()
    documento_venta_id = serializers.IntegerField()
    monto = serializers.DecimalField(max_digits=18, decimal_places=2)
    medio_pago = serializers.ChoiceField(choices=MovimientoCaja.MEDIO_CHOICES)
    observaciones = serializers.CharField(required=False, allow_blank=True)


class PagoProveedorInputSerializer(serializers.Serializer):
    apertura_caja_id = serializers.IntegerField()
    factura_proveedor_id = serializers.IntegerField()
    monto = serializers.DecimalField(max_digits=18, decimal_places=2)
    medio_pago = serializers.ChoiceField(choices=MovimientoCaja.MEDIO_CHOICES)
    observaciones = serializers.CharField(required=False, allow_blank=True)


class MovimientoBancarioInputSerializer(serializers.Serializer):
    cuenta_bancaria_id = serializers.IntegerField()
    tipo = serializers.ChoiceField(choices=MovimientoBancario.TIPO_CHOICES)
    monto = serializers.DecimalField(max_digits=18, decimal_places=2)
    referencia = serializers.CharField(required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)
