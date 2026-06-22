"""
Motor del Copiloto (Módulo 19).

Decisión de diseño deliberada: esto es un router de intenciones por
palabras clave, NO un LLM. Cubre exactamente las preguntas de ejemplo
del enunciado original ("¿Qué productos debo comprar esta semana?",
"¿Qué productos tienen baja rotación?", "¿Cuál fue mi margen el mes
pasado?", "¿Qué clientes disminuyeron sus compras?", "Genera una orden
de compra sugerida") más algunas variantes naturales relacionadas.

Camino de evolución natural: envolver esto con una llamada real a un
modelo de lenguaje (ej. la API de Anthropic) que reciba el catálogo de
intenciones disponibles + los datos ya estructurados que este servicio
devuelve, y los redacte en lenguaje natural más flexible. Eso es una
decisión de producto (requiere una API key y conectividad saliente
desde el servidor) que se deja para que Jorge la habilite cuando quiera,
no se asume acá.
"""
import datetime
import re

from apps.ai_engine.services import InventoryAIService
from apps.analytics.services import DashboardService
from apps.bi.services import BIService

from .models import ConsultaCopiloto

INTENT_PATTERNS = [
    ("generar_orden_compra", [r"genera.*orden de compra", r"crear.*orden de compra", r"orden de compra sugerida"]),
    ("rotacion_lenta", [r"baja rotaci[óo]n", r"rotaci[óo]n lenta", r"no se venden", r"no rotan"]),
    ("clientes_declive", [r"clientes.*(disminuy|bajaron|menos compras|cayeron)"]),
    ("margen_mes_pasado", [r"margen", r"rentabilidad"]),
    ("productos_criticos", [r"stock cr[íi]tico", r"sin stock", r"agotado"]),
    ("productos_obsoletos", [r"obsoleto"]),
    ("top_productos", [r"m[áa]s vendidos", r"top productos"]),
    ("top_clientes", [r"mejores clientes", r"top clientes"]),
    ("inventario_valorizado", [r"inventario valorizado", r"valor del inventario", r"cu[áa]nto vale.*inventario"]),
    ("abc_productos", [r"abc.*productos", r"clasificaci[óo]n abc"]),
    # Estos patrones de "comprar/reponer" van al final porque son los más
    # genéricos ("qué productos...") y deben ceder ante cualquier intent
    # más específico que también mencione la palabra "productos".
    ("comprar_esta_semana", [r"qu[ée] (debo |necesito )?comprar", r"comprar.*(semana|hoy)", r"\breponer\b"]),
]


def _detectar_intent(pregunta: str) -> str:
    pregunta_normalizada = pregunta.lower()
    for intent, patrones in INTENT_PATTERNS:
        for patron in patrones:
            if re.search(patron, pregunta_normalizada):
                return intent
    return "desconocido"


class CopilotoService:
    @classmethod
    def responder(cls, empresa, usuario, pregunta: str) -> dict:
        intent = _detectar_intent(pregunta)
        hoy = datetime.date.today()
        mes_actual_inicio = hoy.replace(day=1)
        mes_pasado_fin = mes_actual_inicio - datetime.timedelta(days=1)
        mes_pasado_inicio = mes_pasado_fin.replace(day=1)

        if intent == "comprar_esta_semana":
            datos = InventoryAIService.productos_para_reponer(empresa)
            if datos:
                nombres = ", ".join(d["codigo"] for d in datos[:5])
                texto = f"Hay {len(datos)} producto(s) en o por debajo del stock mínimo, entre ellos: {nombres}."
            else:
                texto = "Ningún producto está por debajo de su stock mínimo en este momento."

        elif intent == "rotacion_lenta":
            datos = InventoryAIService.productos_rotacion_lenta(empresa)
            texto = (
                f"Hay {len(datos)} producto(s) con stock que no tuvieron salidas en los últimos 90 días."
                if datos else "No se detectaron productos con rotación lenta en los últimos 90 días."
            )

        elif intent == "margen_mes_pasado":
            datos = DashboardService.rentabilidad(empresa, mes_pasado_inicio, mes_pasado_fin)
            texto = (
                f"El mes pasado el margen bruto fue de {datos['margen_bruto_pyg']:,.0f} PYG "
                f"({datos['margen_porcentaje']:.1f}% sobre ventas netas de {datos['ventas_netas_pyg']:,.0f} PYG)."
            )

        elif intent == "clientes_declive":
            datos = BIService.clientes_en_declive(empresa, mes_actual_inicio, hoy)
            if datos:
                nombres = ", ".join((d["nombre_comercial"] or d["razon_social"]) for d in datos[:5])
                texto = f"{len(datos)} cliente(s) bajaron sus compras más de un 20% respecto al período anterior: {nombres}."
            else:
                texto = "No se detectaron clientes con caída significativa de compras en el período actual."

        elif intent == "generar_orden_compra":
            texto = (
                "Para generar la orden de compra sugerida necesito que confirmes la sucursal "
                "(y opcionalmente el proveedor) desde el endpoint "
                "POST /api/ai-engine/reposicion/generar-orden-compra/."
            )
            datos = InventoryAIService.productos_para_reponer(empresa)

        elif intent == "productos_criticos":
            datos = InventoryAIService.productos_criticos(empresa)
            texto = (
                f"{len(datos)} producto(s) están agotados (stock en cero)." if datos
                else "Ningún producto está agotado en este momento."
            )

        elif intent == "productos_obsoletos":
            datos = InventoryAIService.productos_obsoletos(empresa)
            texto = (
                f"{len(datos)} producto(s) tienen stock pero no registran ningún movimiento en 180 días."
                if datos else "No se detectaron productos obsoletos."
            )

        elif intent == "top_productos":
            datos = DashboardService.top_productos_vendidos(empresa, mes_actual_inicio, hoy)
            texto = (
                f"El producto más vendido este mes es {datos[0]['producto__nombre']}." if datos
                else "No hay ventas registradas este mes todavía."
            )

        elif intent == "top_clientes":
            datos = DashboardService.top_clientes(empresa, mes_actual_inicio, hoy)
            texto = (
                f"Tu mejor cliente este mes es {datos[0]['cliente__razon_social']}." if datos
                else "No hay ventas registradas este mes todavía."
            )

        elif intent == "inventario_valorizado":
            datos = DashboardService.inventario_resumen(empresa)
            texto = f"El valor total de tu inventario actual es de {datos['valor_total_inventario_pyg']:,.0f} PYG."

        elif intent == "abc_productos":
            datos = BIService.abc_productos(empresa, mes_actual_inicio, hoy)
            cantidad_a = len([d for d in datos if d["clase_abc"] == "A"])
            texto = f"Tenés {cantidad_a} producto(s) clase A (los que generan el 80% de tus ventas) este mes."

        else:
            datos = None
            texto = (
                "No reconocí esa pregunta todavía. Algunas que sí puedo responder: "
                "'¿Qué productos debo comprar esta semana?', '¿Qué productos tienen baja rotación?', "
                "'¿Cuál fue mi margen el mes pasado?', '¿Qué clientes disminuyeron sus compras?', "
                "'Genera una orden de compra sugerida.'"
            )

        ConsultaCopiloto.objects.create(
            empresa=empresa, usuario=usuario, pregunta=pregunta, intent_detectado=intent, respuesta_resumen=texto,
        )

        return {"intent": intent, "respuesta": texto, "datos": datos}
