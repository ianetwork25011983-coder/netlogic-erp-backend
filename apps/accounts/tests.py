import pyotp
import pytest

from apps.accounts.models import AuditLog, LoginHistory
from apps.accounts.services.mfa_service import MFAService


@pytest.mark.django_db
class TestLoginSinMFA:
    def test_login_correcto_devuelve_tokens(self, api_client, user):
        resp = api_client.post(
            "/api/auth/login/", {"email": "jorge@netlogic.com.py", "password": "Clave123!"}, format="json"
        )
        assert resp.status_code == 200
        assert resp.json()["mfa_required"] is False
        assert "access" in resp.json()
        assert "refresh" in resp.json()

    def test_login_password_incorrecta(self, api_client, user):
        resp = api_client.post(
            "/api/auth/login/", {"email": "jorge@netlogic.com.py", "password": "incorrecta"}, format="json"
        )
        assert resp.status_code == 400

    def test_login_fallido_incrementa_contador_y_bloquea_tras_el_limite(self, api_client, user, settings):
        settings.MAX_LOGIN_ATTEMPTS = 3
        for _ in range(3):
            api_client.post(
                "/api/auth/login/", {"email": "jorge@netlogic.com.py", "password": "incorrecta"}, format="json"
            )
        user.refresh_from_db()
        assert user.is_locked is True

        resp = api_client.post(
            "/api/auth/login/", {"email": "jorge@netlogic.com.py", "password": "Clave123!"}, format="json"
        )
        assert resp.status_code == 400  # bloqueada incluso con password correcta

    def test_login_genera_historial_y_auditoria(self, api_client, user):
        api_client.post("/api/auth/login/", {"email": "jorge@netlogic.com.py", "password": "Clave123!"}, format="json")
        assert LoginHistory.objects.filter(user=user, success=True).exists()
        assert AuditLog.objects.filter(user=user, action=AuditLog.ACTION_LOGIN).exists()


@pytest.mark.django_db
class TestLoginConMFA:
    def _activar_mfa(self, user):
        enrollment = MFAService.start_enrollment(user)
        totp = pyotp.TOTP(enrollment["secret"])
        backup_codes = MFAService.confirm_enrollment(user, totp.now())
        return totp, backup_codes

    def test_login_con_mfa_requiere_segundo_factor(self, api_client, user):
        self._activar_mfa(user)
        resp = api_client.post(
            "/api/auth/login/", {"email": "jorge@netlogic.com.py", "password": "Clave123!"}, format="json"
        )
        assert resp.status_code == 200
        assert resp.json()["mfa_required"] is True
        assert "mfa_token" in resp.json()
        assert "access" not in resp.json()

    def test_segundo_factor_correcto_entrega_tokens(self, api_client, user):
        totp, _ = self._activar_mfa(user)
        resp1 = api_client.post(
            "/api/auth/login/", {"email": "jorge@netlogic.com.py", "password": "Clave123!"}, format="json"
        )
        mfa_token = resp1.json()["mfa_token"]

        resp2 = api_client.post(
            "/api/auth/mfa/verify/", {"mfa_token": mfa_token, "otp_code": totp.now()}, format="json"
        )
        assert resp2.status_code == 200
        assert "access" in resp2.json()

    def test_segundo_factor_incorrecto_rechaza(self, api_client, user):
        self._activar_mfa(user)
        resp1 = api_client.post(
            "/api/auth/login/", {"email": "jorge@netlogic.com.py", "password": "Clave123!"}, format="json"
        )
        mfa_token = resp1.json()["mfa_token"]

        resp2 = api_client.post(
            "/api/auth/mfa/verify/", {"mfa_token": mfa_token, "otp_code": "000000"}, format="json"
        )
        assert resp2.status_code == 400

    def test_codigo_de_respaldo_funciona_una_sola_vez(self, user):
        _, backup_codes = self._activar_mfa(user)
        codigo = backup_codes[0]

        assert MFAService.verify_backup_code(user, codigo) is True
        assert MFAService.verify_backup_code(user, codigo) is False  # ya usado

    def test_secreto_mfa_nunca_se_guarda_en_texto_plano(self, user):
        enrollment = MFAService.start_enrollment(user)
        user.refresh_from_db()
        assert enrollment["secret"] not in user.mfa_secret_encrypted
        assert MFAService.decrypt_secret(user.mfa_secret_encrypted) == enrollment["secret"]


@pytest.mark.django_db
class TestMeEndpoint:
    def test_me_requiere_autenticacion(self, api_client):
        resp = api_client.get("/api/auth/me/")
        assert resp.status_code == 401

    def test_me_devuelve_perfil_propio(self, auth_client, user):
        resp = auth_client.get("/api/auth/me/")
        assert resp.status_code == 200
        assert resp.json()["email"] == user.email
