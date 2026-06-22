from django.contrib import admin

from .models import Despacho, DespachoDocumento, OrdenPacking, OrdenPicking, OrdenPickingItem, Ruta, Transportista, Vehiculo


@admin.register(Transportista)
class TransportistaAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "tipo", "telefono", "active")
    search_fields = ("razon_social", "ruc")
    list_filter = ("tipo", "active", "empresa")
    autocomplete_fields = ("empresa",)


@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = ("placa", "transportista", "marca", "modelo", "capacidad_kg", "active")
    search_fields = ("placa",)
    autocomplete_fields = ("transportista",)


@admin.register(Ruta)
class RutaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "zona", "empresa", "active")
    search_fields = ("nombre",)
    autocomplete_fields = ("empresa",)


class OrdenPickingItemInline(admin.TabularInline):
    model = OrdenPickingItem
    extra = 0
    autocomplete_fields = ("pedido_web_item", "ubicacion")


@admin.register(OrdenPicking)
class OrdenPickingAdmin(admin.ModelAdmin):
    list_display = ("pedido_web", "deposito", "usuario_asignado", "estado", "fecha_inicio", "fecha_fin")
    search_fields = ("pedido_web__numero",)
    list_filter = ("estado", "deposito")
    autocomplete_fields = ("pedido_web", "deposito", "usuario_asignado")
    inlines = [OrdenPickingItemInline]


@admin.register(OrdenPacking)
class OrdenPackingAdmin(admin.ModelAdmin):
    list_display = ("orden_picking", "cantidad_bultos", "peso_total_kg", "volumen_total_m3", "fecha")
    autocomplete_fields = ("orden_picking", "usuario")


class DespachoDocumentoInline(admin.TabularInline):
    model = DespachoDocumento
    extra = 0
    autocomplete_fields = ("documento_venta",)


@admin.register(Despacho)
class DespachoAdmin(admin.ModelAdmin):
    list_display = ("numero", "transportista", "vehiculo", "ruta", "estado", "fecha_despacho")
    search_fields = ("numero",)
    list_filter = ("estado", "transportista", "empresa")
    autocomplete_fields = ("empresa", "transportista", "vehiculo", "ruta", "usuario")
    inlines = [DespachoDocumentoInline]
