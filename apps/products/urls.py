from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("marcas", views.MarcaViewSet, basename="marca")
router.register("categorias", views.CategoriaViewSet, basename="categoria")
router.register("unidades-medida", views.UnidadMedidaViewSet, basename="unidadmedida")
router.register("impuestos", views.ImpuestoViewSet, basename="impuesto")
router.register("productos", views.ProductoViewSet, basename="producto")
router.register("componentes", views.ProductoComponenteViewSet, basename="productocomponente")
router.register("lotes", views.LoteViewSet, basename="lote")
router.register("series", views.SerieViewSet, basename="serie")

urlpatterns = router.urls
