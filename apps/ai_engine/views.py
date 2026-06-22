from django.shortcuts import get_object_or_404
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .services import InventoryAIService


def _get_empresa(request):
    return request.user.empresa


class ProyeccionDemandaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.products.models import Producto

        producto_id = request.query_params.get("producto")
        if not producto_id:
            return Response({"detail": "El parámetro 'producto' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        producto = get_object_or_404(Producto, pk=producto_id)

        meses_adelante = int(request.query_params.get("meses_adelante", 1))
        return Response({
            "historial_mensual": InventoryAIService.historial_ventas_mensual(producto),
            "proyeccion": InventoryAIService.proyeccion_demanda_mensual(producto, meses_adelante=meses_adelante),
            "prediccion_mensual": InventoryAIService.prediccion_mensual(producto, meses_adelante=3),
        })


class SugerirStockMinMaxView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from apps.products.models import Producto

        producto_id = request.query_params.get("producto")
        if not producto_id:
            return Response({"detail": "El parámetro 'producto' es obligatorio."}, status=status.HTTP_400_BAD_REQUEST)
        producto = get_object_or_404(Producto, pk=producto_id)

        lead_time = int(request.query_params.get("lead_time_dias", 7))
        return Response(InventoryAIService.sugerir_stock_minimo_maximo(producto, lead_time_dias=lead_time))


class ProductosParaReponerView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(InventoryAIService.productos_para_reponer(_get_empresa(request)))


class ProductosSobreStockView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(InventoryAIService.productos_sobre_stock(_get_empresa(request)))


class ProductosRotacionLentaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        dias = int(request.query_params.get("dias", 90))
        return Response(InventoryAIService.productos_rotacion_lenta(_get_empresa(request), dias=dias))


class ProductosObsoletosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        dias = int(request.query_params.get("dias", 180))
        return Response(InventoryAIService.productos_obsoletos(_get_empresa(request), dias=dias))


class ProductosCriticosView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(InventoryAIService.productos_criticos(_get_empresa(request)))


class AlertasPreventivasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(InventoryAIService.alertas_preventivas(_get_empresa(request)))


class SugerirTransferenciasView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(InventoryAIService.sugerir_transferencias(_get_empresa(request)))


class GenerarOrdenCompraSugeridaView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        from apps.companies.models import Sucursal
        from apps.suppliers.models import Proveedor

        sucursal = get_object_or_404(Sucursal, pk=request.data.get("sucursal"))
        proveedor = None
        if request.data.get("proveedor"):
            proveedor = get_object_or_404(Proveedor, pk=request.data["proveedor"])

        ordenes = InventoryAIService.generar_orden_compra_sugerida(
            _get_empresa(request), sucursal, request.user, proveedor=proveedor
        )

        from apps.purchases.serializers import OrdenCompraSerializer

        return Response(OrdenCompraSerializer(ordenes, many=True).data, status=status.HTTP_201_CREATED)
