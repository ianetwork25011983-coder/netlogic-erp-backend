from django.contrib import admin

from .models import Currency, ExchangeRate


@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "symbol", "decimal_places", "is_base", "active")
    list_filter = ("active", "is_base")
    search_fields = ("code", "name")
    ordering = ("code",)


@admin.register(ExchangeRate)
class ExchangeRateAdmin(admin.ModelAdmin):
    list_display = ("currency", "rate_to_base", "effective_date", "source", "loaded_by")
    list_filter = ("currency", "source")
    date_hierarchy = "effective_date"
    autocomplete_fields = ("currency", "loaded_by")
    ordering = ("-effective_date",)

    def save_model(self, request, obj, form, change):
        if not obj.loaded_by_id:
            obj.loaded_by = request.user
        super().save_model(request, obj, form, change)
