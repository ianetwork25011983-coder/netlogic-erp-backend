from rest_framework import serializers

from .models import Despacho, DespachoDocumento, OrdenPacking, OrdenPicking, OrdenPickingItem, Ruta, Transportista, Vehiculo


class TransportistaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transportista
        fields = ["id", "empresa", "razon_social", "ruc", "tipo", "telefono", "email", "active"]


class VehiculoSerializer(serializers.ModelSerializer):
    class Meta:
        model = Vehiculo
        fields = ["id", "transportista", "placa", "marca", "modelo", "capacidad_kg", "capacidad_m3", "active"]


class RutaSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ruta
        fields = ["id", "empresa", "nombre", "zona", "active"]


class OrdenPickingItemSerializer(serializers.ModelSerializer):
    producto_codigo = serializers.CharField(source="pedido_web_item.producto.codigo", read_only=True)

    class Meta:
        model = OrdenPickingItem
        fields = ["id", "orden_picking", "pedido_web_item", "producto_codigo", "cantidad_pickeada", "ubicacion"]


class OrdenPickingSerializer(serializers.ModelSerializer):
    items = OrdenPickingItemSerializer(many=True, read_only=True)
    pedido_numero = serializers.CharField(source="pedido_web.numero", read_only=True)

    class Meta:
        model = OrdenPicking
        fields = [
            "id", "pedido_web", "pedido_numero", "deposito", "usuario_asignado",
            "estado", "fecha_inicio", "fecha_fin", "items", "created_at",
        ]
        read_only_fields = ["estado", "fecha_inicio", "fecha_fin", "created_at"]


class OrdenPackingSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrdenPacking
        fields = [
            "id", "orden_picking", "cantidad_bultos", "peso_total_kg",
            "volumen_total_m3", "usuario", "fecha",
        ]
        read_only_fields = ["fecha"]


class DespachoDocumentoSerializer(serializers.ModelSerializer):
    documento_numero = serializers.CharField(source="documento_venta.numero", read_only=True)

    class Meta:
        model = DespachoDocumento
        fields = [
            "id", "despacho", "documento_venta", "documento_numero", "orden_entrega",
            "direccion_entrega", "estado_entrega", "fecha_entrega_real", "firma_recibido", "observaciones",
        ]
        read_only_fields = ["estado_entrega", "fecha_entrega_real"]


class DespachoSerializer(serializers.ModelSerializer):
    documentos = DespachoDocumentoSerializer(many=True, read_only=True)

    class Meta:
        model = Despacho
        fields = [
            "id", "empresa", "numero", "transportista", "vehiculo", "ruta", "conductor_nombre",
            "estado", "usuario", "observaciones", "fecha_despacho", "documentos",
        ]
        read_only_fields = ["numero", "estado", "fecha_despacho"]


# --- Inputs de acción ---

class IniciarPickingInputSerializer(serializers.Serializer):
    pedido_web_id = serializers.IntegerField()
    deposito_id = serializers.IntegerField()
    usuario_asignado_id = serializers.IntegerField(required=False, allow_null=True)


class CompletarPickingItemInputSerializer(serializers.Serializer):
    pedido_web_item_id = serializers.IntegerField()
    cantidad_pickeada = serializers.DecimalField(max_digits=18, decimal_places=4)
    ubicacion_id = serializers.IntegerField(required=False, allow_null=True)


class CompletarPickingInputSerializer(serializers.Serializer):
    items = CompletarPickingItemInputSerializer(many=True)


class CrearPackingInputSerializer(serializers.Serializer):
    cantidad_bultos = serializers.IntegerField(default=1)
    peso_total_kg = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)
    volumen_total_m3 = serializers.DecimalField(max_digits=10, decimal_places=2, required=False, allow_null=True)


class CrearDespachoInputSerializer(serializers.Serializer):
    empresa_id = serializers.IntegerField()
    documentos_venta_ids = serializers.ListField(child=serializers.IntegerField())
    transportista_id = serializers.IntegerField()
    vehiculo_id = serializers.IntegerField(required=False, allow_null=True)
    ruta_id = serializers.IntegerField(required=False, allow_null=True)
    conductor_nombre = serializers.CharField(required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)


class RegistrarEntregaInputSerializer(serializers.Serializer):
    estado_entrega = serializers.ChoiceField(choices=[DespachoDocumento.ESTADO_ENTREGADO, DespachoDocumento.ESTADO_FALLIDO])
    firma_recibido = serializers.CharField(required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)
