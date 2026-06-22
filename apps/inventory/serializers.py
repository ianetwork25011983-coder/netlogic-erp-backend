from decimal import Decimal

from rest_framework import serializers

from .models import CapaCosto, MovimientoInventario, StockBalance, StockReserva, Ubicacion


class UbicacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ubicacion
        fields = ["id", "deposito", "codigo", "rack", "pasillo", "estanteria", "nivel", "descripcion", "active"]


class StockBalanceSerializer(serializers.ModelSerializer):
    producto_codigo = serializers.CharField(source="producto.codigo", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)
    deposito_nombre = serializers.CharField(source="deposito.nombre", read_only=True)
    valor_total_pyg = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = StockBalance
        fields = [
            "id", "producto", "producto_codigo", "producto_nombre", "deposito", "deposito_nombre",
            "lote", "cantidad", "costo_promedio_pyg", "valor_total_pyg", "updated_at",
        ]


class StockReservaSerializer(serializers.ModelSerializer):
    producto_codigo = serializers.CharField(source="producto.codigo", read_only=True)

    class Meta:
        model = StockReserva
        fields = [
            "id", "producto", "producto_codigo", "deposito", "cantidad",
            "referencia_tipo", "referencia_id", "active", "created_at", "released_at",
        ]
        read_only_fields = fields


class CapaCostoSerializer(serializers.ModelSerializer):
    class Meta:
        model = CapaCosto
        fields = [
            "id", "producto", "deposito", "lote", "cantidad_original",
            "cantidad_disponible", "costo_unitario_pyg", "fecha_ingreso", "movimiento_origen",
        ]


class MovimientoInventarioSerializer(serializers.ModelSerializer):
    producto_codigo = serializers.CharField(source="producto.codigo", read_only=True)
    usuario_email = serializers.CharField(source="usuario.email", read_only=True)

    class Meta:
        model = MovimientoInventario
        fields = [
            "id", "producto", "producto_codigo", "deposito", "lote", "ubicacion",
            "tipo_movimiento", "cantidad", "costo_unitario_pyg", "costo_total_pyg",
            "saldo_cantidad_posterior", "saldo_valor_posterior_pyg", "grupo_transferencia",
            "documento_tipo", "documento_referencia", "observaciones", "usuario", "usuario_email", "fecha",
        ]
        read_only_fields = fields


# --- Serializers de entrada para las operaciones del motor (no son ModelSerializer) ---

class EntradaInputSerializer(serializers.Serializer):
    producto = serializers.IntegerField()
    deposito = serializers.IntegerField()
    cantidad = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    costo_unitario = serializers.DecimalField(max_digits=18, decimal_places=6, min_value=0)
    moneda_costo_code = serializers.CharField(max_length=3)
    lote = serializers.IntegerField(required=False, allow_null=True)
    ubicacion = serializers.IntegerField(required=False, allow_null=True)
    documento_tipo = serializers.CharField(max_length=50, required=False, allow_blank=True)
    documento_referencia = serializers.CharField(max_length=100, required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)


class SalidaInputSerializer(serializers.Serializer):
    producto = serializers.IntegerField()
    deposito = serializers.IntegerField()
    cantidad = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    lote = serializers.IntegerField(required=False, allow_null=True)
    ubicacion = serializers.IntegerField(required=False, allow_null=True)
    documento_tipo = serializers.CharField(max_length=50, required=False, allow_blank=True)
    documento_referencia = serializers.CharField(max_length=100, required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)


class TransferenciaInputSerializer(serializers.Serializer):
    producto = serializers.IntegerField()
    deposito_origen = serializers.IntegerField()
    deposito_destino = serializers.IntegerField()
    cantidad = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=Decimal("0.0001"))
    lote = serializers.IntegerField(required=False, allow_null=True)
    ubicacion_destino = serializers.IntegerField(required=False, allow_null=True)
    documento_referencia = serializers.CharField(max_length=100, required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)


class AjusteInputSerializer(serializers.Serializer):
    producto = serializers.IntegerField()
    deposito = serializers.IntegerField()
    cantidad_ajuste = serializers.DecimalField(max_digits=18, decimal_places=4)
    motivo = serializers.CharField()
    lote = serializers.IntegerField(required=False, allow_null=True)
    costo_unitario_manual = serializers.DecimalField(max_digits=18, decimal_places=6, required=False, allow_null=True)
    moneda_costo_code = serializers.CharField(max_length=3, required=False, allow_blank=True)
    documento_referencia = serializers.CharField(max_length=100, required=False, allow_blank=True)

    def validate_cantidad_ajuste(self, value):
        if value == 0:
            raise serializers.ValidationError("La cantidad de ajuste no puede ser cero.")
        return value


class ConteoFisicoInputSerializer(serializers.Serializer):
    producto = serializers.IntegerField()
    deposito = serializers.IntegerField()
    cantidad_contada = serializers.DecimalField(max_digits=18, decimal_places=4, min_value=0)
    lote = serializers.IntegerField(required=False, allow_null=True)
    documento_referencia = serializers.CharField(max_length=100, required=False, allow_blank=True)
