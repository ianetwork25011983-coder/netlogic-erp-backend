"""
Módulo 1 - Seguridad y Accesos.

Decisiones de diseño:
- Login por email (no username).
- Un usuario pertenece a una Empresa "home", pero puede tener acceso a
  varias Sucursales dentro de esa empresa (M2M `sucursales`), con una
  `sucursal_actual` que define el contexto activo de la sesión.
- Los roles NO son fijos a nivel global: un mismo usuario puede tener un
  rol distinto según la empresa/sucursal en la que esté operando
  (RoleAssignment). Esto es clave para operadores que trabajan en más de
  una sucursal con responsabilidades distintas.
- El secreto TOTP de MFA se guarda cifrado (Fernet) a través de
  `services/mfa_service.py`, nunca en texto plano en la base de datos.
"""
from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, Permission, PermissionsMixin
from django.db import models
from django.utils import timezone

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=50, blank=True)

    empresa = models.ForeignKey(
        "companies.Empresa",
        on_delete=models.PROTECT,
        related_name="usuarios",
        null=True,
        blank=True,
        help_text="Empresa principal del usuario. Nulo solo para superusuarios globales.",
    )
    sucursales = models.ManyToManyField(
        "companies.Sucursal",
        related_name="usuarios_con_acceso",
        blank=True,
        help_text="Sucursales a las que este usuario tiene acceso autorizado",
    )
    sucursal_actual = models.ForeignKey(
        "companies.Sucursal",
        on_delete=models.SET_NULL,
        related_name="usuarios_activos_aqui",
        null=True,
        blank=True,
        help_text="Sucursal activa en la sesión actual del usuario",
    )

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # --- MFA ---
    mfa_enabled = models.BooleanField(default=False)
    mfa_secret_encrypted = models.CharField(max_length=255, blank=True)

    # --- Control de acceso / bloqueo ---
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    must_change_password = models.BooleanField(default=True)
    last_password_change = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        ordering = ["email"]

    def __str__(self):
        return f"{self.get_full_name()} <{self.email}>"

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self):
        return self.first_name

    @property
    def is_locked(self):
        return bool(self.locked_until and self.locked_until > timezone.now())

    def has_access_to_sucursal(self, sucursal) -> bool:
        if self.is_superuser:
            return True
        return self.sucursales.filter(pk=sucursal.pk).exists()


class Role(models.Model):
    """
    Rol reutilizable que agrupa permisos granulares de Django
    (django.contrib.auth.models.Permission). El alcance real (a qué
    empresa/sucursal aplica para un usuario dado) se define en
    RoleAssignment, no aquí: el mismo rol "Vendedor" puede asignarse a
    distintos usuarios en distintas sucursales.
    """

    name = models.CharField(max_length=100, unique=True)
    description = models.CharField(max_length=255, blank=True)
    permissions = models.ManyToManyField(Permission, blank=True, related_name="roles")
    is_system_role = models.BooleanField(
        default=False, help_text="Roles base del sistema, no editables/eliminables desde la UI"
    )
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Rol"
        verbose_name_plural = "Roles"
        ordering = ["name"]

    def __str__(self):
        return self.name


class RoleAssignment(models.Model):
    """Asignación de un Rol a un Usuario, con alcance opcional por empresa/sucursal."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="role_assignments")
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="assignments")
    empresa = models.ForeignKey(
        "companies.Empresa", on_delete=models.CASCADE, related_name="role_assignments",
        null=True, blank=True, help_text="Nulo = aplica a todas las empresas del usuario",
    )
    sucursal = models.ForeignKey(
        "companies.Sucursal", on_delete=models.CASCADE, related_name="role_assignments",
        null=True, blank=True, help_text="Nulo = aplica a todas las sucursales permitidas",
    )
    granted_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="role_assignments_granted", null=True
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Asignación de Rol"
        verbose_name_plural = "Asignaciones de Rol"
        ordering = ["-granted_at"]

    def __str__(self):
        scope = self.sucursal or self.empresa or "Global"
        return f"{self.user} -> {self.role} ({scope})"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at < timezone.now())


class MFABackupCode(models.Model):
    """Códigos de recuperación de un solo uso para cuando el usuario pierde el dispositivo TOTP."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="mfa_backup_codes")
    code_hash = models.CharField(max_length=128)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Código de respaldo MFA"
        verbose_name_plural = "Códigos de respaldo MFA"

    @property
    def is_used(self):
        return self.used_at is not None


class LoginHistory(models.Model):
    """Historial de accesos (Módulo 1: 'Historial de accesos')."""

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="login_history", null=True
    )
    email_attempted = models.EmailField(
        help_text="Se guarda aunque el login falle y el email no exista"
    )
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    success = models.BooleanField(default=False)
    mfa_used = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=100, blank=True)

    class Meta:
        verbose_name = "Historial de Acceso"
        verbose_name_plural = "Historial de Accesos"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["user", "-timestamp"]),
            models.Index(fields=["email_attempted", "-timestamp"]),
        ]


class AuditLog(models.Model):
    """
    Auditoría completa de actividad (Módulo 1: 'Auditoría completa' +
    'Registro de actividades'). Pensado para registrar tanto eventos de
    seguridad (login, cambios de permisos) como cambios de datos de
    negocio (creación/edición/borrado de cualquier entidad del ERP).
    """

    ACTION_CREATE = "CREATE"
    ACTION_UPDATE = "UPDATE"
    ACTION_DELETE = "DELETE"
    ACTION_LOGIN = "LOGIN"
    ACTION_LOGOUT = "LOGOUT"
    ACTION_LOGIN_FAILED = "LOGIN_FAILED"
    ACTION_PERMISSION_DENIED = "PERMISSION_DENIED"
    ACTION_MFA_ENABLED = "MFA_ENABLED"
    ACTION_MFA_DISABLED = "MFA_DISABLED"
    ACTION_PASSWORD_RESET = "PASSWORD_RESET"
    ACTION_CHOICES = [
        (ACTION_CREATE, "Creación"),
        (ACTION_UPDATE, "Actualización"),
        (ACTION_DELETE, "Eliminación"),
        (ACTION_LOGIN, "Inicio de sesión"),
        (ACTION_LOGOUT, "Cierre de sesión"),
        (ACTION_LOGIN_FAILED, "Intento de login fallido"),
        (ACTION_PERMISSION_DENIED, "Permiso denegado"),
        (ACTION_MFA_ENABLED, "MFA activado"),
        (ACTION_MFA_DISABLED, "MFA desactivado"),
        (ACTION_PASSWORD_RESET, "Restablecimiento de contraseña"),
    ]

    user = models.ForeignKey(
        User, on_delete=models.SET_NULL, related_name="audit_logs", null=True, blank=True
    )
    action = models.CharField(max_length=30, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    changes = models.JSONField(
        default=dict, blank=True, help_text="Diff {'campo': {'before': ..., 'after': ...}}"
    )
    empresa = models.ForeignKey(
        "companies.Empresa", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    sucursal = models.ForeignKey(
        "companies.Sucursal", on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs"
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Registro de Auditoría"
        verbose_name_plural = "Registros de Auditoría"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["model_name", "object_id"]),
            models.Index(fields=["-timestamp"]),
            models.Index(fields=["user", "-timestamp"]),
        ]

    def __str__(self):
        return f"[{self.timestamp:%Y-%m-%d %H:%M}] {self.user} - {self.action} {self.model_name}"
