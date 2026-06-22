from rest_framework import serializers

from .models import DocumentoVenta, DocumentoVentaItem


class DocumentoVentaItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentoVentaItem
        fields = [
            "id", "documento", "producto", "descripcion", "cantidad", "precio_unitario",
            "descuento_porcentaje", "impuesto", "tasa_impuesto_aplicada",
            "subtotal_linea", "impuesto_linea", "total_linea", "movimiento_inventario",
        ]
        read_only_fields = fields


class DocumentoVentaSerializer(serializers.ModelSerializer):
    items = DocumentoVentaItemSerializer(many=True, read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre_comercial", read_only=True, default=None)

    class Meta:
        model = DocumentoVenta
        fields = [
            "id", "empresa", "sucursal", "punto_venta", "tipo_documento", "numero", "cliente", "cliente_nombre",
            "documento_referencia", "moneda", "tipo_cambio_pyg", "condicion_venta", "estado",
            "afecta_inventario", "deposito_salida", "subtotal", "impuesto_total", "descuento_global", "total", "total_pyg",
            "saldo_pendiente", "fecha_emision", "fecha_vencimiento", "observaciones", "usuario",
            "items", "created_at", "updated_at",
        ]
        read_only_fields = [
            "numero", "tipo_cambio_pyg", "estado", "subtotal", "impuesto_total", "descuento_global",
            "total", "total_pyg", "saldo_pendiente", "created_at", "updated_at",
        ]


# --- Input estructurado para emitir un documento vía BillingService ---

class EmitirDocumentoItemInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()
    cantidad = serializers.DecimalField(max_digits=18, decimal_places=4)
    precio_unitario = serializers.DecimalField(max_digits=18, decimal_places=6)
    descuento_porcentaje = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, default=0)
    impuesto_id = serializers.IntegerField(required=False, allow_null=True)


class EmitirDocumentoInputSerializer(serializers.Serializer):
    empresa = serializers.IntegerField()
    sucursal = serializers.IntegerField()
    punto_venta = serializers.IntegerField()
    tipo_documento = serializers.ChoiceField(choices=DocumentoVenta.TIPO_CHOICES)
    cliente = serializers.IntegerField()
    moneda_code = serializers.CharField(max_length=3)
    items = EmitirDocumentoItemInputSerializer(many=True)
    condicion_venta = serializers.ChoiceField(choices=DocumentoVenta.CONDICION_CHOICES, default=DocumentoVenta.CONDICION_CONTADO)
    fecha_emision = serializers.DateField(required=False, allow_null=True)
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True)
    documento_referencia = serializers.IntegerField(required=False, allow_null=True)
    afecta_inventario = serializers.BooleanField(default=False)
    deposito_salida = serializers.IntegerField(required=False, allow_null=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        if attrs["afecta_inventario"] and not attrs.get("deposito_salida"):
            raise serializers.ValidationError("Si afecta_inventario es true, debe indicar deposito_salida.")
        if attrs["tipo_documento"] in (DocumentoVenta.TIPO_NOTA_CREDITO, DocumentoVenta.TIPO_NOTA_DEBITO) and not attrs.get("documento_referencia"):
            raise serializers.ValidationError("Una Nota de Crédito/Débito debe indicar documento_referencia.")
        return attrs


class AnularDocumentoInputSerializer(serializers.Serializer):
    motivo = serializers.CharField()


class ConvertirPresupuestoInputSerializer(serializers.Serializer):
    punto_venta = serializers.IntegerField()
    afecta_inventario = serializers.BooleanField(default=True)
    deposito_salida = serializers.IntegerField(required=False, allow_null=True)
    condicion_venta = serializers.ChoiceField(choices=DocumentoVenta.CONDICION_CHOICES, default=DocumentoVenta.CONDICION_CONTADO)
