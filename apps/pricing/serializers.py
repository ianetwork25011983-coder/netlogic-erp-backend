from rest_framework import serializers

from .models import Cupon, ListaPrecio, PrecioProducto, Promocion


class PrecioProductoSerializer(serializers.ModelSerializer):
    producto_codigo = serializers.CharField(source="producto.codigo", read_only=True)

    class Meta:
        model = PrecioProducto
        fields = ["id", "lista_precio", "producto", "producto_codigo", "precio"]


class ListaPrecioSerializer(serializers.ModelSerializer):
    precios = PrecioProductoSerializer(many=True, read_only=True)

    class Meta:
        model = ListaPrecio
        fields = ["id", "empresa", "nombre", "moneda", "es_default", "active", "precios"]


class PromocionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Promocion
        fields = [
            "id", "empresa", "nombre", "descuento_porcentaje", "productos",
            "categoria", "vigencia_desde", "vigencia_hasta", "active",
        ]


class CuponSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cupon
        fields = [
            "id", "empresa", "codigo", "tipo_descuento", "valor", "monto_minimo_compra",
            "vigencia_desde", "vigencia_hasta", "usos_maximos", "usos_actuales", "active",
        ]
        read_only_fields = ["usos_actuales"]
