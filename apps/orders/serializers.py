from rest_framework import serializers

from .models import HistorialEstadoPedido, PedidoWeb, PedidoWebItem


class PedidoWebItemSerializer(serializers.ModelSerializer):
    producto_codigo = serializers.CharField(source="producto.codigo", read_only=True)
    producto_nombre = serializers.CharField(source="producto.nombre", read_only=True)

    class Meta:
        model = PedidoWebItem
        fields = [
            "id", "pedido", "producto", "producto_codigo", "producto_nombre",
            "cantidad", "precio_unitario", "descuento_porcentaje", "subtotal_linea",
        ]
        read_only_fields = fields


class HistorialEstadoPedidoSerializer(serializers.ModelSerializer):
    usuario_email = serializers.CharField(source="usuario.email", read_only=True, default=None)

    class Meta:
        model = HistorialEstadoPedido
        fields = ["id", "pedido", "estado_anterior", "estado_nuevo", "usuario", "usuario_email", "nota", "fecha"]
        read_only_fields = fields


class PedidoWebSerializer(serializers.ModelSerializer):
    items = PedidoWebItemSerializer(many=True, read_only=True)
    historial_estados = HistorialEstadoPedidoSerializer(many=True, read_only=True)
    cliente_nombre = serializers.CharField(source="cliente.nombre_comercial", read_only=True, default=None)

    class Meta:
        model = PedidoWeb
        fields = [
            "id", "empresa", "sucursal", "numero", "cliente", "cliente_nombre", "portal_user",
            "lista_precio", "cupon", "deposito_reserva", "estado", "prioridad", "motivo_rechazo",
            "subtotal", "descuento_total", "total", "documento_venta", "observaciones",
            "items", "historial_estados", "fecha_pedido", "updated_at",
        ]
        read_only_fields = [
            "numero", "estado", "motivo_rechazo", "subtotal", "descuento_total", "total",
            "documento_venta", "fecha_pedido", "updated_at",
        ]


# --- Input estructurado para crear un pedido vía OrderService ---

class CrearPedidoItemInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()
    cantidad = serializers.DecimalField(max_digits=18, decimal_places=4)


class CrearPedidoInputSerializer(serializers.Serializer):
    empresa = serializers.IntegerField()
    sucursal = serializers.IntegerField()
    cliente = serializers.IntegerField()
    lista_precio = serializers.IntegerField()
    deposito_reserva = serializers.IntegerField()
    items = CrearPedidoItemInputSerializer(many=True)
    cupon_code = serializers.CharField(required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)


class AccionPedidoInputSerializer(serializers.Serializer):
    nota = serializers.CharField(required=False, allow_blank=True)


class RechazarCancelarPedidoInputSerializer(serializers.Serializer):
    motivo = serializers.CharField()


class FacturarPedidoInputSerializer(serializers.Serializer):
    punto_venta = serializers.IntegerField()
    condicion_venta = serializers.ChoiceField(choices=["CONTADO", "CREDITO"], default="CONTADO")
