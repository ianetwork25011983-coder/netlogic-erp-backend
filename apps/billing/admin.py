from django.contrib import admin

from .models import DocumentoVenta, DocumentoVentaItem, SecuenciaDocumento


@admin.register(SecuenciaDocumento)
class SecuenciaDocumentoAdmin(admin.ModelAdmin):
    list_display = ("punto_venta", "tipo_documento", "ultimo_numero")
    list_filter = ("tipo_documento",)
    autocomplete_fields = ("punto_venta",)


class DocumentoVentaItemInline(admin.TabularInline):
    model = DocumentoVentaItem
    extra = 0
    readonly_fields = [f.name for f in DocumentoVentaItem._meta.fields if f.name != "id"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(DocumentoVenta)
class DocumentoVentaAdmin(admin.ModelAdmin):
    list_display = (
        "numero", "tipo_documento", "cliente", "moneda", "total",
        "total_pyg", "estado", "afecta_inventario", "fecha_emision",
    )
    search_fields = ("numero", "cliente__razon_social", "cliente__nombre_comercial")
    list_filter = ("tipo_documento", "estado", "condicion_venta", "empresa")
    date_hierarchy = "fecha_emision"
    autocomplete_fields = (
        "empresa", "sucursal", "punto_venta", "cliente", "documento_referencia", "moneda", "deposito_salida", "usuario",
    )
    inlines = [DocumentoVentaItemInline]
    readonly_fields = ("numero", "subtotal", "impuesto_total", "descuento_global", "total", "total_pyg", "tipo_cambio_pyg")
