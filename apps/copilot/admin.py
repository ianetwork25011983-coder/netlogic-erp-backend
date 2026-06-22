from django.contrib import admin

from .models import ConsultaCopiloto


@admin.register(ConsultaCopiloto)
class ConsultaCopilotoAdmin(admin.ModelAdmin):
    list_display = ("fecha", "usuario", "intent_detectado", "pregunta")
    search_fields = ("pregunta", "respuesta_resumen")
    list_filter = ("intent_detectado", "empresa")
    readonly_fields = [f.name for f in ConsultaCopiloto._meta.fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False
