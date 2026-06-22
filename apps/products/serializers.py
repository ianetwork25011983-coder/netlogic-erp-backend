from rest_framework import serializers

from .models import Categoria, Impuesto, Lote, Marca, Producto, ProductoComponente, Serie, UnidadMedida


class MarcaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marca
        fields = ["id", "empresa", "nombre", "active"]


class CategoriaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Categoria
        fields = ["id", "empresa", "nombre", "parent", "active"]


class UnidadMedidaSerializer(serializers.ModelSerializer):
    class Meta:
        model = UnidadMedida
        fields = ["id", "codigo", "nombre", "permite_decimales"]


class ImpuestoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Impuesto
        fields = ["id", "nombre", "tasa_porcentaje", "active"]


class ProductoComponenteSerializer(serializers.ModelSerializer):
    componente_codigo = serializers.CharField(source="producto_componente.codigo", read_only=True)
    componente_nombre = serializers.CharField(source="producto_componente.nombre", read_only=True)

    class Meta:
        model = ProductoComponente
        fields = ["id", "producto_padre", "producto_componente", "componente_codigo", "componente_nombre", "cantidad"]


class LoteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lote
        fields = [
            "id", "producto", "numero_lote", "proveedor",
            "fecha_fabricacion", "fecha_vencimiento", "fecha_ingreso", "active",
        ]


class SerieSerializer(serializers.ModelSerializer):
    class Meta:
        model = Serie
        fields = [
            "id", "producto", "numero_serie", "lote", "deposito_actual",
            "estado", "fecha_ingreso", "fecha_egreso",
        ]


class ProductoListSerializer(serializers.ModelSerializer):
    """Versión liviana para listados (sin componentes/lotes anidados)."""

    marca_nombre = serializers.CharField(source="marca.nombre", read_only=True, default=None)
    categoria_nombre = serializers.CharField(source="categoria.nombre", read_only=True, default=None)

    class Meta:
        model = Producto
        fields = [
            "id", "empresa", "tipo", "codigo", "sku", "codigo_barras", "nombre",
            "marca", "marca_nombre", "categoria", "categoria_nombre",
            "moneda_costo", "costo", "moneda_precio", "precio",
            "metodo_costeo", "controla_lote", "controla_serie", "controla_vencimiento",
            "active",
        ]


class ProductoDetailSerializer(serializers.ModelSerializer):
    componentes = ProductoComponenteSerializer(many=True, read_only=True)
    lotes = LoteSerializer(many=True, read_only=True)

    class Meta:
        model = Producto
        fields = [
            "id", "empresa", "tipo", "codigo", "sku", "codigo_barras", "qr_data",
            "nombre", "descripcion", "marca", "categoria", "proveedor_principal",
            "unidad_medida", "impuesto", "moneda_costo", "costo", "moneda_precio", "precio",
            "peso_kg", "volumen_m3", "imagen", "controla_lote", "controla_serie",
            "controla_vencimiento", "metodo_costeo", "stock_minimo", "stock_maximo",
            "stock_seguridad", "active", "componentes", "lotes", "created_at", "updated_at",
        ]
        read_only_fields = ["created_at", "updated_at"]

    def validate(self, attrs):
        def field_value(name):
            return attrs.get(name, getattr(self.instance, name, None) if self.instance else None)

        controla_lote = field_value("controla_lote") or False
        controla_serie = field_value("controla_serie") or False
        controla_vencimiento = field_value("controla_vencimiento") or False

        if controla_serie and controla_lote:
            raise serializers.ValidationError(
                "Un producto no puede controlarse simultáneamente por lote y por serie."
            )
        if controla_vencimiento and not controla_lote:
            raise serializers.ValidationError(
                "El control de vencimiento requiere activar también el control por lote."
            )
        return attrs
