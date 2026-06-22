from rest_framework.routers import DefaultRouter

from django.urls import path

from . import views

router = DefaultRouter()
router.register("documentos", views.DocumentoVentaViewSet, basename="documentoventa")

urlpatterns = [
    path("documentos/emitir/", views.EmitirDocumentoVentaView.as_view(), name="emitir-documento-venta"),
    path("documentos/<int:documento_id>/anular/", views.AnularDocumentoVentaView.as_view(), name="anular-documento-venta"),
    path(
        "documentos/<int:documento_id>/convertir-a-factura/",
        views.ConvertirPresupuestoView.as_view(),
        name="convertir-presupuesto-a-factura",
    ),
    path(
        "documentos/<int:documento_id>/desglose-impuestos/",
        views.DesgloseImpuestosView.as_view(),
        name="desglose-impuestos",
    ),
] + router.urls
