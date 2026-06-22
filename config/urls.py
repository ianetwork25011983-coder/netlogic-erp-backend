from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

urlpatterns = [
    path("admin/", admin.site.urls),
    # Documentación de la API (Módulo 15 - Swagger/OpenAPI)
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path("api/", include("apps.accounts.urls")),
    path("api/", include("apps.companies.urls")),
    path("api/currencies/", include("apps.currencies.urls")),
    path("api/", include("apps.suppliers.urls")),
    path("api/", include("apps.products.urls")),
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/", include("apps.customers.urls")),
    path("api/purchases/", include("apps.purchases.urls")),
    path("api/billing/", include("apps.billing.urls")),
    path("api/pricing/", include("apps.pricing.urls")),
    path("api/crm/", include("apps.crm.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/customer-portal/", include("apps.customer_portal.urls")),
    path("api/treasury/", include("apps.treasury.urls")),
    path("api/logistics/", include("apps.logistics.urls")),
    path("api/analytics/", include("apps.analytics.urls")),
    path("api/reports/", include("apps.reports.urls")),
    path("api/ai-engine/", include("apps.ai_engine.urls")),
    path("api/bi/", include("apps.bi.urls")),
    path("api/copilot/", include("apps.copilot.urls")),
    path("api/automation/", include("apps.automation.urls")),
]
