from django.contrib import admin

from .models import Cliente


@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = ("nombre_comercial", "razon_social", "ruc", "empresa", "es_vip", "dias_credito", "active")
    search_fields = ("razon_social", "nombre_comercial", "ruc")
    list_filter = ("active", "es_vip", "tipo_contribuyente", "empresa")
    autocomplete_fields = ("empresa", "moneda_default")
