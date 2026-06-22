from django.urls import path

from . import views

urlpatterns = [
    path("kardex/excel/", views.KardexExcelView.as_view(), name="kardex-excel"),
    path("inventario-valorizado/excel/", views.InventarioValorizadoExcelView.as_view(), name="inventario-valorizado-excel"),
    path("ventas/excel/", views.VentasExcelView.as_view(), name="ventas-excel"),
    path("compras/excel/", views.ComprasExcelView.as_view(), name="compras-excel"),
    path("clientes/excel/", views.ClientesExcelView.as_view(), name="clientes-excel"),
    path("proveedores/excel/", views.ProveedoresExcelView.as_view(), name="proveedores-excel"),
    path("rentabilidad/excel/", views.RentabilidadExcelView.as_view(), name="rentabilidad-excel"),
    path("documentos/<int:documento_id>/factura.pdf", views.FacturaPdfView.as_view(), name="factura-pdf"),
]
