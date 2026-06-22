from django.contrib.auth import authenticate
from django.core import signing
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .models import Role, RoleAssignment, User
from .services.mfa_service import MFAService

MFA_TOKEN_SALT = "accounts.mfa_pending_token"
MFA_TOKEN_MAX_AGE_SECONDS = 300  # 5 minutos para completar el segundo factor


def issue_tokens_for_user(user):
    refresh = RefreshToken.for_user(user)
    return {"refresh": str(refresh), "access": str(refresh.access_token)}


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate(self, attrs):
        request = self.context.get("request")
        email = attrs["email"].strip().lower()

        user = User.objects.filter(email=email).first()
        if user and user.is_locked:
            raise serializers.ValidationError(
                "Cuenta bloqueada temporalmente por intentos fallidos. Intente más tarde."
            )

        authenticated_user = authenticate(request=request, username=email, password=attrs["password"])
        if authenticated_user is None:
            raise serializers.ValidationError("Email o contraseña incorrectos.")
        if not authenticated_user.is_active:
            raise serializers.ValidationError("Esta cuenta está inactiva.")

        attrs["user"] = authenticated_user
        return attrs

    def to_response(self):
        user = self.validated_data["user"]
        if user.mfa_enabled:
            mfa_token = signing.dumps({"user_id": user.pk}, salt=MFA_TOKEN_SALT)
            return {"mfa_required": True, "mfa_token": mfa_token}

        # Sin MFA: el login se considera completo en este paso. La señal
        # user_logged_in (registro en LoginHistory/AuditLog) se dispara
        # explícitamente desde la vista, no acá.
        tokens = issue_tokens_for_user(user)
        return {"mfa_required": False, **tokens}


class MFAVerifySerializer(serializers.Serializer):
    mfa_token = serializers.CharField()
    otp_code = serializers.CharField(max_length=10)

    def validate(self, attrs):
        try:
            data = signing.loads(
                attrs["mfa_token"], salt=MFA_TOKEN_SALT, max_age=MFA_TOKEN_MAX_AGE_SECONDS
            )
        except signing.BadSignature:
            raise serializers.ValidationError("Token de MFA inválido o expirado. Inicie sesión nuevamente.")

        user = User.objects.filter(pk=data["user_id"], is_active=True).first()
        if user is None:
            raise serializers.ValidationError("Usuario no encontrado o inactivo.")

        is_valid = MFAService.verify_code(user, attrs["otp_code"]) or MFAService.verify_backup_code(
            user, attrs["otp_code"]
        )
        if not is_valid:
            raise serializers.ValidationError("Código de verificación incorrecto.")

        attrs["user"] = user
        return attrs

    def to_response(self):
        user = self.validated_data["user"]
        return {"mfa_required": False, **issue_tokens_for_user(user)}


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Role
        fields = ["id", "name", "description", "permissions", "is_system_role", "active"]


class RoleAssignmentSerializer(serializers.ModelSerializer):
    role_name = serializers.CharField(source="role.name", read_only=True)

    class Meta:
        model = RoleAssignment
        fields = [
            "id", "user", "role", "role_name", "empresa", "sucursal",
            "granted_by", "granted_at", "expires_at", "active",
        ]
        read_only_fields = ["granted_by", "granted_at"]


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "full_name", "phone",
            "empresa", "sucursales", "sucursal_actual", "mfa_enabled",
            "is_active", "must_change_password", "created_at",
        ]
        read_only_fields = ["mfa_enabled", "created_at"]


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = [
            "id", "email", "first_name", "last_name", "phone",
            "empresa", "sucursales", "sucursal_actual", "password",
        ]

    def create(self, validated_data):
        password = validated_data.pop("password")
        sucursales = validated_data.pop("sucursales", [])
        user = User.objects.create_user(password=password, **validated_data)
        if sucursales:
            user.sucursales.set(sucursales)
        return user
