from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/", views.DashboardResumenView.as_view(), name="dashboard-resumen"),
    path("ventas/resumen/", views.VentasResumenView.as_view(), name="ventas-resumen"),
    path("ventas/por-periodo/", views.VentasPorPeriodoView.as_view(), name="ventas-por-periodo"),
    path("ventas/comparativo/", views.ComparativoPeriodoView.as_view(), name="ventas-comparativo"),
    path("ventas/top-productos/", views.TopProductosView.as_view(), name="top-productos"),
    path("ventas/top-clientes/", views.TopClientesView.as_view(), name="top-clientes"),
    path("compras/resumen/", views.ComprasResumenView.as_view(), name="compras-resumen"),
    path("rentabilidad/", views.RentabilidadView.as_view(), name="rentabilidad"),
    path("inventario/resumen/", views.InventarioResumenView.as_view(), name="inventario-resumen-dashboard"),
    path("inventario/rotacion/", views.RotacionInventarioView.as_view(), name="rotacion-inventario"),
]
