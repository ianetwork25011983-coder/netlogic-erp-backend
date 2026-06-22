from rest_framework import serializers

from .models import PortalUser


class PortalLoginInputSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)


class PortalUserSerializer(serializers.ModelSerializer):
    cliente_nombre = serializers.CharField(source="cliente.nombre_comercial", read_only=True)

    class Meta:
        model = PortalUser
        fields = ["id", "cliente", "cliente_nombre", "email", "nombre", "is_active", "last_login_at", "created_at"]


class PortalUserCreateInputSerializer(serializers.Serializer):
    """Usado por personal interno para dar de alta una cuenta de portal a un cliente."""

    cliente_id = serializers.IntegerField()
    email = serializers.EmailField()
    nombre = serializers.CharField(max_length=150)
    password = serializers.CharField(min_length=8, write_only=True)


class PortalChangePasswordInputSerializer(serializers.Serializer):
    password_actual = serializers.CharField(write_only=True)
    password_nueva = serializers.CharField(min_length=8, write_only=True)


class PortalCrearPedidoItemInputSerializer(serializers.Serializer):
    producto_id = serializers.IntegerField()
    cantidad = serializers.DecimalField(max_digits=18, decimal_places=4)


class PortalCrearPedidoInputSerializer(serializers.Serializer):
    sucursal = serializers.IntegerField()
    lista_precio = serializers.IntegerField()
    deposito_reserva = serializers.IntegerField()
    items = PortalCrearPedidoItemInputSerializer(many=True)
    cupon_code = serializers.CharField(required=False, allow_blank=True)
    observaciones = serializers.CharField(required=False, allow_blank=True)
