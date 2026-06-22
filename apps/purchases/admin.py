from django.contrib import admin

from .models import (
    Cotizacion,
    CotizacionItem,
    FacturaProveedor,
    OrdenCompra,
    OrdenCompraItem,
    RecepcionCompra,
    RecepcionCompraItem,
    SolicitudCompra,
    SolicitudCompraItem,
)


class SolicitudCompraItemInline(admin.TabularInline):
    model = SolicitudCompraItem
    extra = 1
    autocomplete_fields = ("producto",)


@admin.register(SolicitudCompra)
class SolicitudCompraAdmin(admin.ModelAdmin):
    list_display = ("numero", "empresa", "sucursal", "solicitante", "estado", "fecha")
    search_fields = ("numero",)
    list_filter = ("estado", "empresa")
    autocomplete_fields = ("empresa", "sucursal", "solicitante")
    inlines = [SolicitudCompraItemInline]


class CotizacionItemInline(admin.TabularInline):
    model = CotizacionItem
    extra = 1
    autocomplete_fields = ("producto",)


@admin.register(Cotizacion)
class CotizacionAdmin(admin.ModelAdmin):
    list_display = ("proveedor", "solicitud", "moneda", "plazo_entrega_dias", "estado", "fecha")
    search_fields = ("proveedor__razon_social", "numero")
    list_filter = ("estado", "empresa")
    autocomplete_fields = ("empresa", "solicitud", "proveedor", "moneda")
    inlines = [CotizacionItemInline]


class OrdenCompraItemInline(admin.TabularInline):
    model = OrdenCompraItem
    extra = 1
    autocomplete_fields = ("producto",)
    readonly_fields = ("cantidad_recibida",)


@admin.register(OrdenCompra)
class OrdenCompraAdmin(admin.ModelAdmin):
    list_display = ("numero", "proveedor", "empresa", "estado", "moneda", "fecha")
    search_fields = ("numero", "proveedor__razon_social")
    list_filter = ("estado", "empresa")
    autocomplete_fields = ("empresa", "sucursal", "proveedor", "cotizacion", "moneda", "usuario")
    inlines = [OrdenCompraItemInline]


class RecepcionCompraItemInline(admin.TabularInline):
    model = RecepcionCompraItem
    extra = 0
    readonly_fields = ("orden_compra_item", "cantidad_recibida", "numero_lote", "fecha_vencimiento", "movimiento_inventario")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(RecepcionCompra)
class RecepcionCompraAdmin(admin.ModelAdmin):
    list_display = ("numero", "orden_compra", "deposito", "usuario", "fecha")
    search_fields = ("numero", "orden_compra__numero")
    list_filter = ("deposito",)
    autocomplete_fields = ("orden_compra", "deposito", "usuario")
    inlines = [RecepcionCompraItemInline]

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(FacturaProveedor)
class FacturaProveedorAdmin(admin.ModelAdmin):
    list_display = ("numero_factura", "proveedor", "monto_total", "saldo_pendiente", "estado", "fecha_emision")
    search_fields = ("numero_factura", "proveedor__razon_social")
    list_filter = ("estado", "empresa")
    autocomplete_fields = ("empresa", "proveedor", "orden_compra", "moneda")
