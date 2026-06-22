"""
Autenticación JWT del Portal de Clientes.

Reutiliza la verificación de firma/expiración de SimpleJWT, pero resuelve
el usuario contra `PortalUser` en vez del `AUTH_USER_MODEL` global, y
exige el claim `portal_user_id` (en vez de `user_id`) para que un token
interno nunca autentique en el portal, ni viceversa.
"""
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import AuthenticationFailed, InvalidToken

from .models import PortalUser


class PortalJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        portal_user_id = validated_token.get("portal_user_id")
        if portal_user_id is None:
            raise InvalidToken("El token no corresponde a una sesión del portal de clientes.")

        try:
            return PortalUser.objects.select_related("cliente", "cliente__empresa").get(
                pk=portal_user_id, is_active=True
            )
        except PortalUser.DoesNotExist:
            raise AuthenticationFailed("Usuario del portal no encontrado o inactivo.")
