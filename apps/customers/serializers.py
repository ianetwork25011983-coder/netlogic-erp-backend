from rest_framework import serializers

from .models import Cliente


class ClienteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cliente
        fields = [
            "id", "empresa", "razon_social", "nombre_comercial", "ruc", "tipo_contribuyente",
            "contacto_nombre", "telefono", "email", "direccion",
            "moneda_default", "limite_credito", "dias_credito", "es_vip", "active",
        ]
