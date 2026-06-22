import pytest
from rest_framework_simplejwt.tokens import RefreshToken

from apps.customer_portal.models import PortalUser


@pytest.fixture
def portal_user(db, cliente):
    pu = PortalUser(cliente=cliente, email="compras@abc.com", nombre="Ana Pérez")
    pu.set_password("PortalClave123!")
    pu.save()
    return pu


@pytest.mark.django_db
class TestPortalLogin:
    def test_login_correcto_devuelve_tokens(self, api_client, portal_user):
        resp = api_client.post(
            "/api/customer-portal/auth/login/", {"email": "compras@abc.com", "password": "PortalClave123!"}, format="json"
        )
        assert resp.status_code == 200
        assert "access" in resp.json()

    def test_login_password_incorrecta_rechaza(self, api_client, portal_user):
        resp = api_client.post(
            "/api/customer-portal/auth/login/", {"email": "compras@abc.com", "password": "incorrecta"}, format="json"
        )
        assert resp.status_code == 400

    def test_login_cuenta_inactiva_rechaza(self, api_client, portal_user):
        portal_user.is_active = False
        portal_user.save()
        resp = api_client.post(
            "/api/customer-portal/auth/login/", {"email": "compras@abc.com", "password": "PortalClave123!"}, format="json"
        )
        assert resp.status_code == 400


@pytest.mark.django_db
class TestAislamientoDeAutenticacion:
    """El test de seguridad más importante del portal: un token nunca debe servir para el otro lado."""

    def test_token_de_portal_no_autentica_endpoint_interno(self, api_client, portal_user):
        resp_login = api_client.post(
            "/api/customer-portal/auth/login/", {"email": "compras@abc.com", "password": "PortalClave123!"}, format="json"
        )
        access = resp_login.json()["access"]

        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        resp = api_client.get("/api/auth/me/")
        assert resp.status_code == 401

    def test_token_interno_no_autentica_endpoint_de_portal(self, api_client, user):
        token = RefreshToken.for_user(user).access_token
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        resp = api_client.get("/api/customer-portal/auth/me/")
        assert resp.status_code == 401

    def test_portal_user_solo_ve_sus_propios_pedidos(self, api_client, portal_user, cliente, empresa, pyg):
        from apps.customers.models import Cliente

        Cliente.objects.create(empresa=empresa, razon_social="Otro Cliente", ruc="80055555-5", moneda_default=pyg)

        resp_login = api_client.post(
            "/api/customer-portal/auth/login/", {"email": "compras@abc.com", "password": "PortalClave123!"}, format="json"
        )
        access = resp_login.json()["access"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")

        resp = api_client.get("/api/customer-portal/pedidos/")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.django_db
class TestPortalProvisioning:
    def test_personal_interno_puede_provisionar_cuenta_de_portal(self, auth_client, cliente):
        resp = auth_client.post(
            "/api/customer-portal/admin/provisionar-usuario/",
            {"cliente_id": cliente.id, "email": "nuevo@cliente.com", "nombre": "Test User", "password": "ClaveSegura123!"},
            format="json",
        )
        assert resp.status_code == 201
        assert PortalUser.objects.filter(email="nuevo@cliente.com").exists()

    def test_password_se_guarda_hasheada(self, cliente):
        pu = PortalUser(cliente=cliente, email="test@test.com", nombre="Test")
        pu.set_password("MiClaveSecreta")
        assert pu.password_hash != "MiClaveSecreta"
        assert pu.check_password("MiClaveSecreta") is True
        assert pu.check_password("incorrecta") is False
