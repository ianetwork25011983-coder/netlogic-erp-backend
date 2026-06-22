from django.contrib import admin

from .models import Alerta, EjecucionRegla, ReglaAutomatizacion


@admin.register(ReglaAutomatizacion)
class ReglaAutomatizacionAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "tipo_entidad", "evaluar_en", "accion", "active", "ultima_ejecucion")
    search_fields = ("nombre",)
    list_filter = ("tipo_entidad", "evaluar_en", "accion", "active", "empresa")
    autocomplete_fields = ("empresa",)
    readonly_fields = ("ultima_ejecucion",)


@admin.register(Alerta)
class AlertaAdmin(admin.ModelAdmin):
    list_display = ("mensaje_corto", "empresa", "regla", "leida", "fecha")
    search_fields = ("mensaje",)
    list_filter = ("leida", "empresa")
    autocomplete_fields = ("empresa", "regla")

    def mensaje_corto(self, obj):
        return obj.mensaje[:80]


@admin.register(EjecucionRegla)
class EjecucionReglaAdmin(admin.ModelAdmin):
    list_display = ("regla", "objeto_tipo", "objeto_id", "condicion_cumplida", "accion_ejecutada", "fecha")
    search_fields = ("objeto_id",)
    list_filter = ("condicion_cumplida", "accion_ejecutada", "regla")
    readonly_fields = [f.name for f in EjecucionRegla._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
