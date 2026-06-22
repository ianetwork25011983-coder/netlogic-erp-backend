from django.contrib import admin

from .models import HistorialEstadoPedido, PedidoWeb, PedidoWebItem


class PedidoWebItemInline(admin.TabularInline):
    model = PedidoWebItem
    extra = 0
    readonly_fields = ("subtotal_linea",)
    autocomplete_fields = ("producto",)


class HistorialEstadoPedidoInline(admin.TabularInline):
    model = HistorialEstadoPedido
    extra = 0
    readonly_fields = ("estado_anterior", "estado_nuevo", "usuario", "nota", "fecha")

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PedidoWeb)
class PedidoWebAdmin(admin.ModelAdmin):
    list_display = ("numero", "cliente", "estado", "prioridad", "total", "deposito_reserva", "fecha_pedido")
    search_fields = ("numero", "cliente__razon_social")
    list_filter = ("estado", "prioridad", "empresa")
    autocomplete_fields = (
        "empresa", "sucursal", "cliente", "portal_user", "lista_precio",
        "cupon", "deposito_reserva", "documento_venta",
    )
    inlines = [PedidoWebItemInline, HistorialEstadoPedidoInline]
    readonly_fields = ("numero", "subtotal", "descuento_total", "total")


@admin.register(PedidoWebItem)
class PedidoWebItemAdmin(admin.ModelAdmin):
    list_display = ("pedido", "producto", "cantidad", "precio_unitario", "subtotal_linea")
    search_fields = ("pedido__numero", "producto__codigo")
    autocomplete_fields = ("pedido", "producto")
