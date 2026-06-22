from django.shortcuts import get_object_or_404
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Contacto, EtapaPipeline, Interaccion, Oportunidad, Prospecto
from .serializers import (
    ContactoSerializer,
    ConvertirProspectoInputSerializer,
    EtapaPipelineSerializer,
    InteraccionSerializer,
    MoverEtapaInputSerializer,
    OportunidadSerializer,
    ProspectoSerializer,
)
from .services import CRMError, CRMService


class ScopedToEmpresaMixin:
    empresa_lookup = "empresa"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if user.is_superuser:
            return qs
        return qs.filter(**{self.empresa_lookup: user.empresa})


class ProspectoViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Prospecto.objects.select_related("empresa", "responsable", "cliente_convertido").prefetch_related("contactos")
    serializer_class = ProspectoSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["estado", "responsable"]


class ConvertirProspectoView(APIView):
    """POST /api/crm/prospectos/<id>/convertir/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, prospecto_id):
        serializer = ConvertirProspectoInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qs = Prospecto.objects.all() if request.user.is_superuser else Prospecto.objects.filter(empresa=request.user.empresa)
        prospecto = get_object_or_404(qs, pk=prospecto_id)

        from apps.currencies.models import Currency

        moneda = get_object_or_404(Currency, pk=data["moneda_default_id"])

        try:
            cliente = CRMService.convertir_prospecto_a_cliente(
                prospecto, ruc=data["ruc"], moneda_default=moneda, tipo_contribuyente=data["tipo_contribuyente"],
                dias_credito=data.get("dias_credito", 0), limite_credito=data.get("limite_credito", 0),
            )
        except CRMError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        from apps.customers.serializers import ClienteSerializer

        return Response(ClienteSerializer(cliente).data, status=status.HTTP_201_CREATED)


class ContactoViewSet(viewsets.ModelViewSet):
    queryset = Contacto.objects.select_related("cliente", "prospecto")
    serializer_class = ContactoSerializer
    permission_classes = [permissions.IsAuthenticated]


class EtapaPipelineViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = EtapaPipeline.objects.select_related("empresa")
    serializer_class = EtapaPipelineSerializer
    permission_classes = [permissions.IsAuthenticated]


class OportunidadViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Oportunidad.objects.select_related("empresa", "cliente", "prospecto", "etapa_pipeline", "moneda", "responsable")
    serializer_class = OportunidadSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["estado", "etapa_pipeline", "responsable"]


class MoverEtapaOportunidadView(APIView):
    """POST /api/crm/oportunidades/<id>/mover-etapa/"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, oportunidad_id):
        serializer = MoverEtapaInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        qs = Oportunidad.objects.all() if request.user.is_superuser else Oportunidad.objects.filter(empresa=request.user.empresa)
        oportunidad = get_object_or_404(qs, pk=oportunidad_id)
        etapa = get_object_or_404(EtapaPipeline, pk=data["etapa_pipeline_id"])

        oportunidad = CRMService.mover_oportunidad_etapa(oportunidad, etapa, data.get("motivo_perdida", ""))
        return Response(OportunidadSerializer(oportunidad).data)


class PipelineResumenView(APIView):
    """GET /api/crm/pipeline/resumen/ -- cantidad y valor de oportunidades abiertas por etapa."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        empresa = request.user.empresa
        if not empresa and not request.user.is_superuser:
            return Response({"detail": "El usuario no tiene empresa asignada."}, status=status.HTTP_400_BAD_REQUEST)
        return Response(CRMService.pipeline_resumen(empresa))


class InteraccionViewSet(ScopedToEmpresaMixin, viewsets.ModelViewSet):
    queryset = Interaccion.objects.select_related("empresa", "cliente", "prospecto", "oportunidad", "usuario")
    serializer_class = InteraccionSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_fields = ["tipo", "cliente", "prospecto", "completada"]

    def perform_create(self, serializer):
        serializer.save(usuario=self.request.user)
