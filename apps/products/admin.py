from django.contrib import admin

from .models import Categoria, Impuesto, Lote, Marca, Producto, ProductoComponente, Serie, UnidadMedida


@admin.register(Marca)
class MarcaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "active")
    search_fields = ("nombre",)
    list_filter = ("active", "empresa")
    autocomplete_fields = ("empresa",)


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "parent", "empresa", "active")
    search_fields = ("nombre",)
    list_filter = ("active", "empresa")
    autocomplete_fields = ("empresa", "parent")


@admin.register(UnidadMedida)
class UnidadMedidaAdmin(admin.ModelAdmin):
    list_display = ("codigo", "nombre", "permite_decimales")
    search_fields = ("codigo", "nombre")


@admin.register(Impuesto)
class ImpuestoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "tasa_porcentaje", "active")
    search_fields = ("nombre",)


class ProductoComponenteInline(admin.TabularInline):
    model = ProductoComponente
    fk_name = "producto_padre"
    extra = 1
    autocomplete_fields = ("producto_componente",)


class LoteInline(admin.TabularInline):
    model = Lote
    extra = 0
    fields = ("numero_lote", "fecha_vencimiento", "proveedor", "active")


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = (
        "codigo", "nombre", "tipo", "empresa", "marca", "categoria",
        "costo", "precio", "metodo_costeo", "active",
    )
    search_fields = ("codigo", "sku", "codigo_barras", "nombre")
    list_filter = ("tipo", "active", "metodo_costeo", "empresa", "marca", "categoria")
    autocomplete_fields = (
        "empresa", "marca", "categoria", "proveedor_principal",
        "unidad_medida", "impuesto", "moneda_costo", "moneda_precio",
    )
    inlines = [ProductoComponenteInline, LoteInline]
    fieldsets = (
        (None, {"fields": ("empresa", "tipo", "codigo", "sku", "codigo_barras", "qr_data", "nombre", "descripcion")}),
        ("Clasificación", {"fields": ("marca", "categoria", "proveedor_principal", "unidad_medida", "impuesto")}),
        ("Costos y precios", {"fields": ("moneda_costo", "costo", "moneda_precio", "precio")}),
        ("Logística", {"fields": ("peso_kg", "volumen_m3", "imagen")}),
        ("Trazabilidad e inventario", {
            "fields": (
                "controla_lote", "controla_serie", "controla_vencimiento", "metodo_costeo",
                "stock_minimo", "stock_maximo", "stock_seguridad",
            ),
        }),
        ("Estado", {"fields": ("active",)}),
    )


@admin.register(Lote)
class LoteAdmin(admin.ModelAdmin):
    list_display = ("producto", "numero_lote", "fecha_vencimiento", "proveedor", "active")
    search_fields = ("numero_lote", "producto__codigo", "producto__nombre")
    list_filter = ("active",)
    autocomplete_fields = ("producto", "proveedor")


@admin.register(Serie)
class SerieAdmin(admin.ModelAdmin):
    list_display = ("producto", "numero_serie", "estado", "deposito_actual", "lote")
    search_fields = ("numero_serie", "producto__codigo", "producto__nombre")
    list_filter = ("estado", "deposito_actual")
    autocomplete_fields = ("producto", "lote", "deposito_actual")
