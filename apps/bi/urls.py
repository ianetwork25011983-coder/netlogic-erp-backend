from django.urls import path

from . import views

urlpatterns = [
    path("abc/productos/", views.AbcProductosView.as_view(), name="abc-productos"),
    path("abc/clientes/", views.AbcClientesView.as_view(), name="abc-clientes"),
    path("clientes-en-declive/", views.ClientesEnDeclive.as_view(), name="clientes-en-declive"),
    path("rotacion-por-categoria/", views.RotacionPorCategoriaView.as_view(), name="rotacion-por-categoria"),
]
