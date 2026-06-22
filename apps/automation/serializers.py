from rest_framework import serializers

from .models import Alerta, EjecucionRegla, ReglaAutomatizacion


class ReglaAutomatizacionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ReglaAutomatizacion
        fields = [
            "id", "empresa", "nombre", "descripcion", "tipo_entidad", "evaluar_en", "frecuencia_horas",
            "condiciones", "accion", "parametros_accion", "active", "ultima_ejecucion", "created_at",
        ]
        read_only_fields = ["ultima_ejecucion", "created_at"]


class AlertaSerializer(serializers.ModelSerializer):
    regla_nombre = serializers.CharField(source="regla.nombre", read_only=True, default=None)

    class Meta:
        model = Alerta
        fields = ["id", "empresa", "regla", "regla_nombre", "objeto_tipo", "objeto_id", "mensaje", "leida", "fecha"]
        read_only_fields = ["fecha"]


class EjecucionReglaSerializer(serializers.ModelSerializer):
    class Meta:
        model = EjecucionRegla
        fields = [
            "id", "regla", "objeto_tipo", "objeto_id", "condicion_cumplida",
            "accion_ejecutada", "contexto_evaluado", "resultado", "fecha",
        ]
        read_only_fields = fields


class EvaluarProductoInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()


class EvaluarPedidoInputSerializer(serializers.Serializer):
    pedido_web_id = serializers.IntegerField()
