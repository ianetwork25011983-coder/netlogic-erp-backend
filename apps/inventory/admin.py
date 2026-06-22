from django.contrib import admin

from .models import CapaCosto, MovimientoInventario, StockBalance, StockReserva, Ubicacion


@admin.register(Ubicacion)
class UbicacionAdmin(admin.ModelAdmin):
    list_display = ("codigo", "deposito", "rack", "pasillo", "estanteria", "nivel", "active")
    search_fields = ("codigo", "deposito__nombre")
    list_filter = ("active", "deposito")
    autocomplete_fields = ("deposito",)


@admin.register(StockBalance)
class StockBalanceAdmin(admin.ModelAdmin):
    list_display = ("producto", "deposito", "lote", "cantidad", "costo_promedio_pyg", "valor_total_pyg")
    search_fields = ("producto__codigo", "producto__nombre")
    list_filter = ("deposito",)
    autocomplete_fields = ("producto", "deposito", "lote")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CapaCosto)
class CapaCostoAdmin(admin.ModelAdmin):
    list_display = (
        "producto", "deposito", "lote", "cantidad_disponible",
        "cantidad_original", "costo_unitario_pyg", "fecha_ingreso",
    )
    search_fields = ("producto__codigo", "producto__nombre")
    list_filter = ("deposito",)
    date_hierarchy = "fecha_ingreso"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(StockReserva)
class StockReservaAdmin(admin.ModelAdmin):
    list_display = ("producto", "deposito", "cantidad", "referencia_tipo", "referencia_id", "active", "created_at")
    search_fields = ("producto__codigo", "referencia_id")
    list_filter = ("active", "referencia_tipo", "deposito")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(MovimientoInventario)
class MovimientoInventarioAdmin(admin.ModelAdmin):
    list_display = (
        "fecha", "tipo_movimiento", "producto", "deposito", "cantidad",
        "costo_unitario_pyg", "costo_total_pyg", "saldo_cantidad_posterior", "usuario",
    )
    search_fields = ("producto__codigo", "producto__nombre", "documento_referencia")
    list_filter = ("tipo_movimiento", "deposito")
    date_hierarchy = "fecha"
    readonly_fields = [f.name for f in MovimientoInventario._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
