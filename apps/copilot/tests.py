import pytest

from apps.copilot.models import ConsultaCopiloto
from apps.copilot.services import CopilotoService


@pytest.mark.django_db
class TestDeteccionDeIntencion:
    @pytest.mark.parametrize("pregunta,intent_esperado", [
        ("¿Qué productos debo comprar esta semana?", "comprar_esta_semana"),
        ("¿Qué productos tienen baja rotación?", "rotacion_lenta"),
        ("¿Cuál fue mi margen el mes pasado?", "margen_mes_pasado"),
        ("¿Qué clientes disminuyeron sus compras?", "clientes_declive"),
        ("Genera una orden de compra sugerida.", "generar_orden_compra"),
        ("¿Qué productos están obsoletos?", "productos_obsoletos"),
        ("¿Cuáles son mis productos más vendidos?", "top_productos"),
        ("¿Quiénes son mis mejores clientes?", "top_clientes"),
        ("¿Cuánto vale mi inventario?", "inventario_valorizado"),
        ("Pregunta sin sentido sobre el clima", "desconocido"),
    ])
    def test_detecta_el_intent_correcto(self, empresa, user, pregunta, intent_esperado):
        resultado = CopilotoService.responder(empresa, user, pregunta)
        assert resultado["intent"] == intent_esperado

    def test_cada_consulta_queda_registrada_en_bitacora(self, empresa, user):
        CopilotoService.responder(empresa, user, "¿Qué productos debo comprar esta semana?")
        assert ConsultaCopiloto.objects.filter(empresa=empresa, usuario=user).count() == 1

    def test_pregunta_sin_match_devuelve_sugerencias(self, empresa, user):
        resultado = CopilotoService.responder(empresa, user, "qué clima hace hoy")
        assert "No reconocí esa pregunta" in resultado["respuesta"]


@pytest.mark.django_db
class TestEndpointCopiloto:
    def test_preguntar_via_api(self, auth_client):
        resp = auth_client.post("/api/copilot/preguntar/", {"pregunta": "¿Qué productos debo comprar esta semana?"}, format="json")
        assert resp.status_code == 200
        assert "respuesta" in resp.json()

    def test_historial_via_api(self, auth_client):
        auth_client.post("/api/copilot/preguntar/", {"pregunta": "test"}, format="json")
        resp = auth_client.get("/api/copilot/historial/")
        assert resp.status_code == 200
        assert len(resp.json()) == 1
