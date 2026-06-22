from django.contrib import admin

from .models import Proveedor


@admin.register(Proveedor)
class ProveedorAdmin(admin.ModelAdmin):
    list_display = ("nombre_comercial", "razon_social", "ruc", "empresa", "active")
    search_fields = ("razon_social", "nombre_comercial", "ruc")
    list_filter = ("active", "empresa")
    autocomplete_fields = ("empresa", "moneda_default")
