from rest_framework import serializers

from .models import Proveedor


class ProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = Proveedor
        fields = [
            "id", "empresa", "razon_social", "nombre_comercial", "ruc",
            "contacto_nombre", "telefono", "email", "direccion",
            "moneda_default", "active",
        ]
