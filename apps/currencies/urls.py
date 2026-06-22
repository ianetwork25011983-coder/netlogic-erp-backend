from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("currencies", views.CurrencyViewSet, basename="currency")
router.register("exchange-rates", views.ExchangeRateViewSet, basename="exchangerate")

urlpatterns = [
    path("convert/", views.ConvertAmountView.as_view(), name="currency-convert"),
] + router.urls
