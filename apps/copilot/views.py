from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import ConsultaCopiloto
from .serializers import ConsultaCopilotoSerializer, PreguntarInputSerializer
from .services import CopilotoService


class PreguntarView(APIView):
    """POST /api/copilot/preguntar/ {"pregunta": "..."}"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = PreguntarInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        empresa = request.user.empresa
        if not empresa:
            return Response(
                {"detail": "El usuario no tiene empresa asignada."}, status=status.HTTP_400_BAD_REQUEST
            )

        resultado = CopilotoService.responder(empresa, request.user, serializer.validated_data["pregunta"])
        return Response(resultado)


class HistorialConsultasView(APIView):
    """GET /api/copilot/historial/ -- consultas propias recientes."""

    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        consultas = ConsultaCopiloto.objects.filter(usuario=request.user).order_by("-fecha")[:50]
        return Response(ConsultaCopilotoSerializer(consultas, many=True).data)
