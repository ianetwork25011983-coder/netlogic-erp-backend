from django.contrib import admin

from .models import Deposito, Empresa, PuntoVenta, Sucursal


class SucursalInline(admin.TabularInline):
    model = Sucursal
    extra = 0
    fields = ("codigo", "nombre", "es_casa_matriz", "active")


@admin.register(Empresa)
class EmpresaAdmin(admin.ModelAdmin):
    list_display = ("razon_social", "nombre_comercial", "ruc", "moneda_default", "active")
    search_fields = ("razon_social", "nombre_comercial", "ruc")
    list_filter = ("active", "tipo_contribuyente", "moneda_default")
    autocomplete_fields = ("moneda_default",)
    inlines = [SucursalInline]


class DepositoInline(admin.TabularInline):
    model = Deposito
    extra = 0
    fields = ("codigo", "nombre", "tipo", "active")


class PuntoVentaInline(admin.TabularInline):
    model = PuntoVenta
    extra = 0
    fields = ("codigo", "nombre", "establecimiento", "punto_expedicion", "active")


@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "empresa", "es_casa_matriz", "active")
    search_fields = ("nombre", "codigo", "empresa__razon_social")
    list_filter = ("active", "es_casa_matriz", "empresa")
    autocomplete_fields = ("empresa",)
    inlines = [DepositoInline, PuntoVentaInline]


@admin.register(Deposito)
class DepositoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "sucursal", "tipo", "active")
    search_fields = ("nombre", "codigo")
    list_filter = ("tipo", "active", "sucursal__empresa")
    autocomplete_fields = ("sucursal",)


@admin.register(PuntoVenta)
class PuntoVentaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "sucursal", "establecimiento", "punto_expedicion", "active")
    search_fields = ("nombre", "codigo")
    list_filter = ("active", "sucursal__empresa")
    autocomplete_fields = ("sucursal", "deposito_predeterminado")
