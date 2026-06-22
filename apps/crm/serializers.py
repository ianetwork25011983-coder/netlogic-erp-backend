from rest_framework import serializers

from .models import Contacto, EtapaPipeline, Interaccion, Oportunidad, Prospecto


class ContactoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Contacto
        fields = ["id", "cliente", "prospecto", "nombre", "cargo", "telefono", "email", "es_principal", "notas"]

    def validate(self, attrs):
        cliente = attrs.get("cliente", getattr(self.instance, "cliente", None))
        prospecto = attrs.get("prospecto", getattr(self.instance, "prospecto", None))
        if bool(cliente) == bool(prospecto):
            raise serializers.ValidationError("Debe indicar exactamente un Cliente o un Prospecto, no ambos.")
        return attrs


class ProspectoSerializer(serializers.ModelSerializer):
    contactos = ContactoSerializer(many=True, read_only=True)

    class Meta:
        model = Prospecto
        fields = [
            "id", "empresa", "razon_social", "nombre_comercial", "contacto_nombre", "telefono", "email",
            "origen", "estado", "responsable", "notas", "cliente_convertido", "fecha_conversion",
            "contactos", "created_at", "updated_at",
        ]
        read_only_fields = ["estado", "cliente_convertido", "fecha_conversion", "created_at", "updated_at"]


class EtapaPipelineSerializer(serializers.ModelSerializer):
    class Meta:
        model = EtapaPipeline
        fields = ["id", "empresa", "nombre", "orden", "es_ganada", "es_perdida", "active"]


class OportunidadSerializer(serializers.ModelSerializer):
    etapa_nombre = serializers.CharField(source="etapa_pipeline.nombre", read_only=True)

    class Meta:
        model = Oportunidad
        fields = [
            "id", "empresa", "cliente", "prospecto", "nombre", "etapa_pipeline", "etapa_nombre",
            "valor_estimado", "moneda", "probabilidad_porcentaje", "fecha_cierre_estimada",
            "responsable", "estado", "motivo_perdida", "created_at", "updated_at",
        ]
        read_only_fields = ["estado", "motivo_perdida", "created_at", "updated_at"]

    def validate(self, attrs):
        cliente = attrs.get("cliente", getattr(self.instance, "cliente", None))
        prospecto = attrs.get("prospecto", getattr(self.instance, "prospecto", None))
        if bool(cliente) == bool(prospecto):
            raise serializers.ValidationError("Debe indicar exactamente un Cliente o un Prospecto, no ambos.")
        return attrs


class InteraccionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Interaccion
        fields = [
            "id", "empresa", "cliente", "prospecto", "oportunidad", "tipo", "descripcion",
            "usuario", "fecha", "fecha_proxima_accion", "completada",
        ]
        read_only_fields = ["fecha"]


class MoverEtapaInputSerializer(serializers.Serializer):
    etapa_pipeline_id = serializers.IntegerField()
    motivo_perdida = serializers.CharField(required=False, allow_blank=True)


class ConvertirProspectoInputSerializer(serializers.Serializer):
    ruc = serializers.CharField(max_length=20)
    moneda_default_id = serializers.IntegerField()
    tipo_contribuyente = serializers.ChoiceField(choices=["FISICA", "JURIDICA", "EXTRANJERO"], default="FISICA")
    dias_credito = serializers.IntegerField(required=False, default=0)
    limite_credito = serializers.DecimalField(max_digits=18, decimal_places=2, required=False, default=0)
