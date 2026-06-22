from django.contrib import admin

from .models import Contacto, EtapaPipeline, Interaccion, Oportunidad, Prospecto


class ContactoInline(admin.TabularInline):
    model = Contacto
    extra = 0
    fk_name = "prospecto"
    fields = ("nombre", "cargo", "telefono", "email", "es_principal")


@admin.register(Prospecto)
class ProspectoAdmin(admin.ModelAdmin):
    list_display = ("nombre_comercial", "razon_social", "estado", "origen", "responsable", "empresa")
    search_fields = ("razon_social", "nombre_comercial", "email")
    list_filter = ("estado", "empresa")
    autocomplete_fields = ("empresa", "responsable", "cliente_convertido")
    inlines = [ContactoInline]


@admin.register(Contacto)
class ContactoAdmin(admin.ModelAdmin):
    list_display = ("nombre", "cargo", "cliente", "prospecto", "es_principal")
    search_fields = ("nombre", "email")
    autocomplete_fields = ("cliente", "prospecto")


@admin.register(EtapaPipeline)
class EtapaPipelineAdmin(admin.ModelAdmin):
    list_display = ("nombre", "empresa", "orden", "es_ganada", "es_perdida", "active")
    search_fields = ("nombre",)
    list_filter = ("empresa", "active")
    autocomplete_fields = ("empresa",)


@admin.register(Oportunidad)
class OportunidadAdmin(admin.ModelAdmin):
    list_display = (
        "nombre", "cliente", "prospecto", "etapa_pipeline", "valor_estimado",
        "moneda", "probabilidad_porcentaje", "estado", "responsable",
    )
    search_fields = ("nombre",)
    list_filter = ("estado", "etapa_pipeline", "empresa")
    autocomplete_fields = ("empresa", "cliente", "prospecto", "etapa_pipeline", "moneda", "responsable")


@admin.register(Interaccion)
class InteraccionAdmin(admin.ModelAdmin):
    list_display = ("tipo", "cliente", "prospecto", "oportunidad", "usuario", "fecha", "completada")
    search_fields = ("descripcion",)
    list_filter = ("tipo", "completada", "empresa")
    autocomplete_fields = ("empresa", "cliente", "prospecto", "oportunidad", "usuario")
    date_hierarchy = "fecha"
