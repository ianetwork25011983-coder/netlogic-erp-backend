from django.urls import path

from . import views

urlpatterns = [
    path("demanda/proyeccion/", views.ProyeccionDemandaView.as_view(), name="proyeccion-demanda"),
    path("reposicion/sugerir-min-max/", views.SugerirStockMinMaxView.as_view(), name="sugerir-stock-min-max"),
    path("reposicion/productos-a-reponer/", views.ProductosParaReponerView.as_view(), name="productos-a-reponer"),
    path("reposicion/sugerir-transferencias/", views.SugerirTransferenciasView.as_view(), name="sugerir-transferencias"),
    path("reposicion/generar-orden-compra/", views.GenerarOrdenCompraSugeridaView.as_view(), name="generar-orden-compra-sugerida"),
    path("anomalias/sobre-stock/", views.ProductosSobreStockView.as_view(), name="productos-sobre-stock"),
    path("anomalias/rotacion-lenta/", views.ProductosRotacionLentaView.as_view(), name="productos-rotacion-lenta"),
    path("anomalias/obsoletos/", views.ProductosObsoletosView.as_view(), name="productos-obsoletos"),
    path("anomalias/criticos/", views.ProductosCriticosView.as_view(), name="productos-criticos"),
    path("alertas-preventivas/", views.AlertasPreventivasView.as_view(), name="alertas-preventivas"),
]
