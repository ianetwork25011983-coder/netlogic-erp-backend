from rest_framework import serializers

from .models import ConsultaCopiloto


class PreguntarInputSerializer(serializers.Serializer):
    pregunta = serializers.CharField()


class ConsultaCopilotoSerializer(serializers.ModelSerializer):
    class Meta:
        model = ConsultaCopiloto
        fields = ["id", "usuario", "pregunta", "intent_detectado", "respuesta_resumen", "fecha"]
        read_only_fields = fields
