from django.contrib import admin

from .models import Cupon, ListaPrecio, PrecioProducto, Promocion


class PrecioProductoInline(admin.TabularInline):
    model = PrecioProducto
    extra = 1
    autocomplete_fields = ("producto",)


@admin.register(ListaPrecio)
class ListaPrecioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "moneda", "es_default", "active")
    search_fields = ("nombre",)
    list_filter = ("active", "empresa")
    autocomplete_fields = ("empresa", "moneda")
    inlines = [PrecioProductoInline]


@admin.register(Promocion)
class PromocionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "descuento_porcentaje", "categoria", "vigencia_desde", "vigencia_hasta", "active")
    search_fields = ("nombre",)
    list_filter = ("active", "empresa")
    autocomplete_fields = ("empresa", "categoria", "productos")


@admin.register(Cupon)
class CuponAdmin(admin.ModelAdmin):
    list_display = ("codigo", "tipo_descuento", "valor", "usos_actuales", "usos_maximos", "vigencia_hasta", "active")
    search_fields = ("codigo",)
    list_filter = ("active", "tipo_descuento", "empresa")
    autocomplete_fields = ("empresa",)
