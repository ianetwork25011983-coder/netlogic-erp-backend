from rest_framework import serializers

from .models import Deposito, Empresa, PuntoVenta, Sucursal


class EmpresaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Empresa
        fields = [
            "id", "razon_social", "nombre_comercial", "ruc", "tipo_contribuyente",
            "timbrado_numero", "timbrado_vencimiento", "moneda_default",
            "direccion", "telefono", "email", "logo", "active",
        ]


class DepositoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Deposito
        fields = [
            "id", "sucursal", "codigo", "nombre", "tipo",
            "ubicacion_fisica", "permite_venta_directa", "active",
        ]


class PuntoVentaSerializer(serializers.ModelSerializer):
    class Meta:
        model = PuntoVenta
        fields = [
            "id", "sucursal", "codigo", "nombre", "establecimiento",
            "punto_expedicion", "deposito_predeterminado", "active",
        ]


class SucursalSerializer(serializers.ModelSerializer):
    depositos = DepositoSerializer(many=True, read_only=True)
    puntos_venta = PuntoVentaSerializer(many=True, read_only=True)

    class Meta:
        model = Sucursal
        fields = [
            "id", "empresa", "codigo", "nombre", "direccion", "telefono",
            "es_casa_matriz", "active", "depositos", "puntos_venta",
        ]
