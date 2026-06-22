from django.contrib.auth.signals import user_logged_in
from rest_framework import generics, permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import AuditLog, LoginHistory, Role, RoleAssignment, User
from .serializers import (
    LoginSerializer,
    MFAVerifySerializer,
    RoleAssignmentSerializer,
    RoleSerializer,
    UserCreateSerializer,
    UserSerializer,
)
from .services.audit_service import AuditService
from .services.mfa_service import MFAService


class LoginView(APIView):
    """
    POST /api/auth/login/
    Si el usuario no tiene MFA, devuelve directamente access/refresh.
    Si tiene MFA activo, devuelve {"mfa_required": true, "mfa_token": ...}
    y el cliente debe llamar a /api/auth/mfa/verify/ con ese token + el OTP.
    """

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        response_data = serializer.to_response()

        if not response_data["mfa_required"]:
            user_logged_in.send(sender=User, request=request, user=serializer.validated_data["user"])

        return Response(response_data, status=status.HTTP_200_OK)


class MFAVerifyView(APIView):
    """POST /api/auth/mfa/verify/ -- segundo factor, entrega los tokens JWT finales."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = MFAVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        response_data = serializer.to_response()
        user_logged_in.send(sender=User, request=request, user=user)
        return Response(response_data, status=status.HTTP_200_OK)


class MFAEnrollView(APIView):
    """POST /api/auth/mfa/enroll/ -- usuario autenticado inicia el alta de MFA."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        result = MFAService.start_enrollment(request.user)
        return Response(result, status=status.HTTP_200_OK)


class MFAEnrollConfirmView(APIView):
    """POST /api/auth/mfa/enroll/confirm/ -- confirma el primer código y activa MFA."""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        otp_code = request.data.get("otp_code", "")
        backup_codes = MFAService.confirm_enrollment(request.user, otp_code)
        if backup_codes is None:
            return Response({"detail": "Código incorrecto."}, status=status.HTTP_400_BAD_REQUEST)

        AuditService.log(AuditLog.ACTION_MFA_ENABLED, user=request.user, request=request)
        return Response(
            {"mfa_enabled": True, "backup_codes": backup_codes},
            status=status.HTTP_200_OK,
        )


class MFADisableView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        MFAService.disable(request.user)
        AuditService.log(AuditLog.ACTION_MFA_DISABLED, user=request.user, request=request)
        return Response({"mfa_enabled": False}, status=status.HTTP_200_OK)


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)


class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.select_related("empresa", "sucursal_actual").all()
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_superuser:
            qs = qs.filter(empresa=self.request.user.empresa)
        return qs


class RoleViewSet(viewsets.ModelViewSet):
    queryset = Role.objects.all()
    serializer_class = RoleSerializer
    permission_classes = [permissions.IsAuthenticated]


class RoleAssignmentViewSet(viewsets.ModelViewSet):
    queryset = RoleAssignment.objects.select_related("user", "role", "empresa", "sucursal")
    serializer_class = RoleAssignmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        serializer.save(granted_by=self.request.user)


class LoginHistoryListView(generics.ListAPIView):
    """Historial de accesos del propio usuario autenticado."""

    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return LoginHistory.objects.filter(user=self.request.user)[:50]

    def list(self, request, *args, **kwargs):
        data = [
            {
                "timestamp": h.timestamp,
                "ip_address": h.ip_address,
                "success": h.success,
                "mfa_used": h.mfa_used,
            }
            for h in self.get_queryset()
        ]
        return Response(data)
