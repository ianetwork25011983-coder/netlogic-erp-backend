from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import AuditLog, LoginHistory, MFABackupCode, Role, RoleAssignment, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    ordering = ("email",)
    list_display = (
        "email", "first_name", "last_name", "empresa", "sucursal_actual",
        "mfa_enabled", "is_active", "is_staff",
    )
    list_filter = ("is_active", "is_staff", "mfa_enabled", "empresa")
    search_fields = ("email", "first_name", "last_name")
    filter_horizontal = ("sucursales", "groups", "user_permissions")
    autocomplete_fields = ("empresa", "sucursal_actual")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Datos personales", {"fields": ("first_name", "last_name", "phone")}),
        ("Contexto organizacional", {
            "fields": ("empresa", "sucursales", "sucursal_actual"),
        }),
        ("Seguridad", {
            "fields": (
                "mfa_enabled", "failed_login_attempts", "locked_until",
                "must_change_password", "last_password_change",
            ),
        }),
        ("Permisos", {
            "fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions"),
        }),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "first_name", "last_name", "empresa", "password1", "password2"),
        }),
    )
    readonly_fields = ("last_password_change",)


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "is_system_role", "active")
    search_fields = ("name",)
    filter_horizontal = ("permissions",)


@admin.register(RoleAssignment)
class RoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "empresa", "sucursal", "active", "expires_at")
    list_filter = ("active", "role", "empresa")
    search_fields = ("user__email", "role__name")
    autocomplete_fields = ("user", "role", "empresa", "sucursal", "granted_by")


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ("email_attempted", "timestamp", "success", "mfa_used", "ip_address")
    list_filter = ("success", "mfa_used")
    search_fields = ("email_attempted", "ip_address")
    date_hierarchy = "timestamp"
    readonly_fields = [f.name for f in LoginHistory._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("timestamp", "user", "action", "model_name", "object_repr", "empresa", "sucursal")
    list_filter = ("action", "model_name", "empresa")
    search_fields = ("user__email", "object_repr", "model_name")
    date_hierarchy = "timestamp"
    readonly_fields = [f.name for f in AuditLog._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MFABackupCode)
class MFABackupCodeAdmin(admin.ModelAdmin):
    list_display = ("user", "created_at", "used_at")
    readonly_fields = ("code_hash", "created_at", "used_at")
    search_fields = ("user__email",)
