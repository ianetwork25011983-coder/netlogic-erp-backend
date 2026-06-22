from rest_framework import serializers

from .models import (
    Cotizacion,
    CotizacionItem,
    FacturaProveedor,
    OrdenCompra,
    OrdenCompraItem,
    RecepcionCompra,
    RecepcionCompraItem,
    SolicitudCompra,
    SolicitudCompraItem,
)


class SolicitudCompraItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SolicitudCompraItem
        fields = ["id", "solicitud", "producto", "cantidad", "observacion"]


class SolicitudCompraSerializer(serializers.ModelSerializer):
    items = SolicitudCompraItemSerializer(many=True, read_only=True)

    class Meta:
        model = SolicitudCompra
        fields = [
            "id", "empresa", "sucursal", "numero", "solicitante",
            "estado", "observaciones", "fecha", "items",
        ]
        read_only_fields = ["fecha"]


class CotizacionItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)

    class Meta:
        model = CotizacionItem
        fields = ["id", "cotizacion", "producto", "cantidad", "precio_unitario", "descuento_porcentaje", "subtotal"]


class CotizacionSerializer(serializers.ModelSerializer):
    items = CotizacionItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    proveedor_nombre = serializers.CharField(source="proveedor.nombre_comercial", read_only=True)

    class Meta:
        model = Cotizacion
        fields = [
            "id", "empresa", "solicitud", "proveedor", "proveedor_nombre", "numero", "moneda",
            "plazo_entrega_dias", "condiciones_pago", "vigencia_hasta", "estado", "fecha", "items", "total",
        ]
        read_only_fields = ["fecha"]


class OrdenCompraItemSerializer(serializers.ModelSerializer):
    subtotal = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    cantidad_pendiente = serializers.DecimalField(max_digits=18, decimal_places=4, read_only=True)
    producto_codigo = serializers.CharField(source="producto.codigo", read_only=True)

    class Meta:
        model = OrdenCompraItem
        fields = [
            "id", "orden_compra", "producto", "producto_codigo", "cantidad", "precio_unitario",
            "descuento_porcentaje", "cantidad_recibida", "cantidad_pendiente", "subtotal",
        ]
        read_only_fields = ["cantidad_recibida"]


class OrdenCompraSerializer(serializers.ModelSerializer):
    items = OrdenCompraItemSerializer(many=True, read_only=True)
    total = serializers.DecimalField(max_digits=20, decimal_places=2, read_only=True)
    proveedor_nombre = serializers.CharField(source="proveedor.nombre_comercial", read_only=True)

    class Meta:
        model = OrdenCompra
        fields = [
            "id", "empresa", "sucursal", "proveedor", "proveedor_nombre", "cotizacion", "numero",
            "moneda", "condiciones_pago", "estado", "observaciones", "usuario", "fecha", "items", "total",
        ]
        read_only_fields = ["numero", "estado", "fecha"]


class OrdenCompraItemInputSerializer(serializers.Serializer):
    """Item de entrada para crear una orden de compra manual (sin pasar por cotización)."""

    producto = serializers.IntegerField()
    cantidad = serializers.DecimalField(max_digits=18, decimal_places=4)
    precio_unitario = serializers.DecimalField(max_digits=18, decimal_places=6)
    descuento_porcentaje = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, default=0)


class OrdenCompraCreateSerializer(serializers.ModelSerializer):
    """Para creación manual (sin pasar por una cotización)."""

    items = OrdenCompraItemInputSerializer(many=True)

    class Meta:
        model = OrdenCompra
        fields = [
            "id", "empresa", "sucursal", "proveedor", "numero", "moneda",
            "condiciones_pago", "observaciones", "items",
        ]
        read_only_fields = ["numero"]

    def create(self, validated_data):
        from apps.products.models import Producto

        from .services import PurchaseService

        items_data = validated_data.pop("items")
        validated_data["numero"] = PurchaseService.generar_numero_orden_compra(validated_data["empresa"])
        validated_data["usuario"] = self.context["request"].user
        orden = OrdenCompra.objects.create(**validated_data)
        for item in items_data:
            producto = Producto.objects.get(pk=item["producto"])
            OrdenCompraItem.objects.create(
                orden_compra=orden,
                producto=producto,
                cantidad=item["cantidad"],
                precio_unitario=item["precio_unitario"],
                descuento_porcentaje=item.get("descuento_porcentaje", 0),
            )
        return orden


class RecepcionCompraItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = RecepcionCompraItem
        fields = [
            "id", "recepcion", "orden_compra_item", "cantidad_recibida",
            "numero_lote", "fecha_vencimiento", "movimiento_inventario",
        ]
        read_only_fields = fields


class RecepcionCompraSerializer(serializers.ModelSerializer):
    items = RecepcionCompraItemSerializer(many=True, read_only=True)

    class Meta:
        model = RecepcionCompra
        fields = ["id", "orden_compra", "deposito", "numero", "usuario", "observaciones", "fecha", "items"]
        read_only_fields = ["numero", "fecha"]


class RecepcionItemInputSerializer(serializers.Serializer):
    orden_compra_item_id = serializers.IntegerField()
    cantidad_recibida = serializers.DecimalField(max_digits=18, decimal_places=4)
    numero_lote = serializers.CharField(required=False, allow_blank=True)
    fecha_vencimiento = serializers.DateField(required=False, allow_null=True)


class RecibirOrdenInputSerializer(serializers.Serializer):
    orden_compra = serializers.IntegerField()
    deposito = serializers.IntegerField()
    items = RecepcionItemInputSerializer(many=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)


class FacturaProveedorSerializer(serializers.ModelSerializer):
    class Meta:
        model = FacturaProveedor
        fields = [
            "id", "empresa", "proveedor", "orden_compra", "numero_factura", "timbrado_proveedor",
            "moneda", "monto_total", "saldo_pendiente", "fecha_emision", "fecha_vencimiento",
            "estado", "observaciones", "created_at",
        ]
        read_only_fields = ["saldo_pendiente", "created_at"]
