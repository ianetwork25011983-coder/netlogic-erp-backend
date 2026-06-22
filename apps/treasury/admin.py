from django.contrib import admin

from .models import AperturaCaja, Banco, Caja, CierreCaja, CuentaBancaria, MovimientoBancario, MovimientoCaja


@admin.register(Caja)
class CajaAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo", "sucursal", "punto_venta", "active")
    search_fields = ("nombre", "codigo")
    list_filter = ("active", "sucursal")
    autocomplete_fields = ("empresa", "sucursal", "punto_venta")


class MovimientoCajaInline(admin.TabularInline):
    model = MovimientoCaja
    extra = 0
    readonly_fields = [f.name for f in MovimientoCaja._meta.fields if f.name != "id"]

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(AperturaCaja)
class AperturaCajaAdmin(admin.ModelAdmin):
    list_display = ("caja", "usuario", "monto_inicial", "moneda", "estado", "fecha_apertura")
    list_filter = ("estado", "caja")
    autocomplete_fields = ("caja", "usuario", "moneda")
    inlines = [MovimientoCajaInline]


@admin.register(MovimientoCaja)
class MovimientoCajaAdmin(admin.ModelAdmin):
    list_display = ("apertura_caja", "tipo", "concepto", "medio_pago", "monto", "moneda", "fecha")
    list_filter = ("tipo", "concepto", "medio_pago")
    search_fields = ("referencia_id",)
    date_hierarchy = "fecha"
    readonly_fields = [f.name for f in MovimientoCaja._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CierreCaja)
class CierreCajaAdmin(admin.ModelAdmin):
    list_display = ("apertura_caja", "monto_contado_efectivo", "monto_esperado_efectivo", "diferencia", "fecha_cierre")
    readonly_fields = [f.name for f in CierreCaja._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Banco)
class BancoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "active")
    search_fields = ("nombre",)


@admin.register(CuentaBancaria)
class CuentaBancariaAdmin(admin.ModelAdmin):
    list_display = ("banco", "numero_cuenta", "tipo_cuenta", "moneda", "saldo_actual", "active")
    search_fields = ("numero_cuenta",)
    list_filter = ("active", "banco", "empresa")
    autocomplete_fields = ("empresa", "banco", "moneda")
    readonly_fields = ("saldo_actual",)


@admin.register(MovimientoBancario)
class MovimientoBancarioAdmin(admin.ModelAdmin):
    list_display = ("cuenta_bancaria", "tipo", "monto", "saldo_posterior", "fecha")
    list_filter = ("tipo", "cuenta_bancaria")
    readonly_fields = [f.name for f in MovimientoBancario._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
