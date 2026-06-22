import datetime
from io import BytesIO

from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .pdf import generar_factura_pdf
from .services import ReportService

XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _excel_response(workbook, filename):
    buffer = BytesIO()
    workbook.save(buffer)
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type=XLSX_CONTENT_TYPE)
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _parse_fechas(request):
    hoy = datetime.date.today()
    desde_str = request.query_params.get("desde")
    hasta_str = request.query_params.get("hasta")
    fecha_desde = datetime.date.fromisoformat(desde_str) if desde_str else hoy.replace(day=1)
    fecha_hasta = datetime.date.fromisoformat(hasta_str) if hasta_str else hoy
    return fecha_desde, fecha_hasta


class KardexExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.companies.models import Deposito
        from apps.products.models import Producto

        producto_id = request.query_params.get("producto")
        if not producto_id:
            return Response({"detail": "El parámetro 'producto' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)

        producto = get_object_or_404(Producto, pk=producto_id)
        deposito = None
        if request.query_params.get("deposito"):
            deposito = get_object_or_404(Deposito, pk=request.query_params["deposito"])

        wb = ReportService.kardex_excel(producto, deposito=deposito)
        return _excel_response(wb, f"kardex_{producto.codigo}.xlsx")


class InventarioValorizadoExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.companies.models import Deposito

        empresa = request.user.empresa
        deposito = None
        if request.query_params.get("deposito"):
            deposito = get_object_or_404(Deposito, pk=request.query_params["deposito"])

        wb = ReportService.inventario_valorizado_excel(empresa, deposito=deposito)
        return _excel_response(wb, "inventario_valorizado.xlsx")


class VentasExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        fecha_desde, fecha_hasta = _parse_fechas(request)
        wb = ReportService.ventas_excel(request.user.empresa, fecha_desde, fecha_hasta)
        return _excel_response(wb, f"ventas_{fecha_desde}_{fecha_hasta}.xlsx")


class ComprasExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        fecha_desde, fecha_hasta = _parse_fechas(request)
        wb = ReportService.compras_excel(request.user.empresa, fecha_desde, fecha_hasta)
        return _excel_response(wb, f"compras_{fecha_desde}_{fecha_hasta}.xlsx")


class ClientesExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wb = ReportService.clientes_excel(request.user.empresa)
        return _excel_response(wb, "clientes.xlsx")


class ProveedoresExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        wb = ReportService.proveedores_excel(request.user.empresa)
        return _excel_response(wb, "proveedores.xlsx")


class RentabilidadExcelView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        fecha_desde, fecha_hasta = _parse_fechas(request)
        wb = ReportService.rentabilidad_excel(request.user.empresa, fecha_desde, fecha_hasta)
        return _excel_response(wb, f"rentabilidad_{fecha_desde}_{fecha_hasta}.xlsx")


class FacturaPdfView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, documento_id):
        from apps.billing.models import DocumentoVenta

        qs = DocumentoVenta.objects.all() if request.user.is_superuser else DocumentoVenta.objects.filter(empresa=request.user.empresa)
        documento = get_object_or_404(qs, pk=documento_id)

        pdf_bytes = generar_factura_pdf(documento)
        response = HttpResponse(pdf_bytes, content_type="application/pdf")
        response["Content-Disposition"] = f'inline; filename="{documento.numero}.pdf"'
        return response
