from django.contrib import admin

from .models import PortalUser


@admin.register(PortalUser)
class PortalUserAdmin(admin.ModelAdmin):
    list_display = ("email", "nombre", "cliente", "is_active", "last_login_at")
    search_fields = ("email", "nombre", "cliente__razon_social")
    list_filter = ("is_active",)
    autocomplete_fields = ("cliente",)
    fields = ("cliente", "email", "nombre", "is_active", "last_login_at", "created_at")
    readonly_fields = ("last_login_at", "created_at")
