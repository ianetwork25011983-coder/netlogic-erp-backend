"""
Módulo 7 - Portal de Clientes.

`PortalUser` es deliberadamente independiente de `accounts.User`
(empleados internos): un cliente puede tener varios contactos con acceso
al portal, y no deben mezclarse con los roles/permisos internos del ERP
ni con `request.empresa`/`request.sucursal` del middleware interno. La
autenticación usa JWT igual que el resto de la API, pero con un claim
propio (`portal_user_id`) y una clase de autenticación separada
(`PortalJWTAuthentication`, en `auth.py`) para que un token de portal
nunca pueda usarse en los endpoints internos, ni viceversa.
"""
from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class PortalUser(models.Model):
    cliente = models.ForeignKey("customers.Cliente", on_delete=models.CASCADE, related_name="usuarios_portal")
    email = models.EmailField(unique=True)
    password_hash = models.CharField(max_length=255)
    nombre = models.CharField(max_length=150)
    is_active = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Usuario de Portal"
        verbose_name_plural = "Usuarios de Portal"
        ordering = ["email"]

    def __str__(self):
        return f"{self.nombre} <{self.email}> ({self.cliente})"

    def set_password(self, raw_password):
        self.password_hash = make_password(raw_password)

    def check_password(self, raw_password) -> bool:
        return check_password(raw_password, self.password_hash)

    @property
    def is_authenticated(self):
        """Permite usar permissions.IsAuthenticated estándar de DRF con este modelo."""
        return True

    @property
    def is_anonymous(self):
        return False
