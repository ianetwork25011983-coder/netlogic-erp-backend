"""
Motor de Automatizaciones (Módulo 16).

`evaluar_producto()` y `evaluar_pedido_web()` son los puntos de entrada:
construyen el "contexto" (diccionario de campos disponibles para ese
tipo de entidad) y evalúan contra él todas las `ReglaAutomatizacion`
activas de ese tipo. Cada evaluación queda registrada en
`EjecucionRegla`, se cumpla o no la condición, para poder auditar por
qué una regla disparó (o no disparó) en un caso puntual.
"""
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from .models import Alerta, EjecucionRegla, ReglaAutomatizacion


class RuleEngineError(Exception):
    pass


_OPERADORES = {
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
}


class RuleEngineService:
    @staticmethod
    def _construir_contexto_producto(producto):
        from apps.inventory.models import MovimientoInventario

        stock_actual = sum((s.cantidad for s in producto.saldos.all()), Decimal("0"))
        ultimo_movimiento = MovimientoInventario.objects.filter(producto=producto).order_by("-fecha").first()
        dias_sin_movimiento = (
            (timezone.now() - ultimo_movimiento.fecha).days if ultimo_movimiento else 99999
        )

        return {
            "stock_actual": float(stock_actual),
            "stock_minimo": float(producto.stock_minimo),
            "stock_maximo": float(producto.stock_maximo),
            "stock_seguridad": float(producto.stock_seguridad),
            "dias_sin_movimiento": dias_sin_movimiento,
            "costo": float(producto.costo),
            "precio": float(producto.precio),
        }

    @staticmethod
    def _construir_contexto_pedido_web(pedido):
        return {
            "total": float(pedido.total),
            "cliente_es_vip": bool(pedido.cliente.es_vip),
            "cantidad_items": pedido.items.count(),
            "estado": pedido.estado,
        }

    @staticmethod
    def _evaluar_condiciones(condiciones, contexto) -> bool:
        for condicion in condiciones:
            campo = condicion["campo"]
            operador = condicion["operador"]
            if campo not in contexto:
                return False
            valor_real = contexto[campo]

            if "campo_comparacion" in condicion:
                campo_comp = condicion["campo_comparacion"]
                if campo_comp not in contexto:
                    return False
                valor_esperado = contexto[campo_comp]
            else:
                valor_esperado = condicion["valor"]

            funcion = _OPERADORES.get(operador)
            if funcion is None:
                raise RuleEngineError(f"Operador no soportado: {operador}")
            if not funcion(valor_real, valor_esperado):
                return False
        return True

    @classmethod
    def _ejecutar_accion(cls, regla, objeto, contexto):
        if regla.accion == ReglaAutomatizacion.ACCION_GENERAR_ALERTA:
            mensaje = regla.parametros_accion.get("mensaje") or f"Se cumplió la regla '{regla.nombre}' para {objeto}."
            Alerta.objects.create(
                empresa=regla.empresa, regla=regla, objeto_tipo=objeto.__class__.__name__,
                objeto_id=str(objeto.pk), mensaje=mensaje,
            )
            return f"Alerta generada: {mensaje}"

        if regla.accion == ReglaAutomatizacion.ACCION_GENERAR_SOLICITUD_COMPRA:
            from apps.accounts.models import User
            from apps.companies.models import Sucursal
            from apps.purchases.models import SolicitudCompra, SolicitudCompraItem

            sucursal_id = regla.parametros_accion.get("sucursal_id")
            if sucursal_id:
                sucursal_obj = Sucursal.objects.get(pk=sucursal_id)
            else:
                sucursal_obj = Sucursal.objects.filter(empresa=regla.empresa, active=True).first()

            solicitante_id = regla.parametros_accion.get("solicitante_id")
            if solicitante_id:
                solicitante = User.objects.get(pk=solicitante_id)
            else:
                # Sin solicitante configurado en la regla: se usa el primer
                # usuario staff de la empresa como responsable nominal de
                # la solicitud autogenerada (queda igual auditado en
                # `observaciones` que fue creada por la regla, no por una persona).
                solicitante = User.objects.filter(empresa=regla.empresa, is_staff=True).first()
                if solicitante is None:
                    raise RuleEngineError(
                        f"La regla '{regla.nombre}' no tiene 'solicitante_id' configurado en "
                        "parametros_accion y la empresa no tiene ningún usuario staff disponible "
                        "como responsable por defecto."
                    )

            solicitud = SolicitudCompra.objects.create(
                empresa=regla.empresa, sucursal=sucursal_obj,
                numero=f"AUTO-{regla.id}-{objeto.pk}-{int(timezone.now().timestamp())}",
                solicitante=solicitante, estado=SolicitudCompra.ESTADO_BORRADOR,
                observaciones=f"Generada automáticamente por la regla '{regla.nombre}'.",
            )
            cantidad_sugerida = max(
                Decimal(str(contexto.get("stock_maximo", 0))) - Decimal(str(contexto.get("stock_actual", 0))),
                Decimal(str(contexto.get("stock_minimo", 0))),
            )
            SolicitudCompraItem.objects.create(
                solicitud=solicitud, producto=objeto, cantidad=cantidad_sugerida or Decimal("1"),
                observacion="Cantidad sugerida automáticamente.",
            )
            return f"Solicitud de compra {solicitud.numero} generada."

        if regla.accion == ReglaAutomatizacion.ACCION_ASIGNAR_PRIORIDAD:
            from apps.orders.models import PedidoWeb

            prioridad = regla.parametros_accion.get("prioridad", PedidoWeb.PRIORIDAD_ALTA)
            objeto.prioridad = prioridad
            objeto.save(update_fields=["prioridad"])
            return f"Prioridad asignada: {prioridad}"

        raise RuleEngineError(f"Acción no soportada: {regla.accion}")

    @classmethod
    @transaction.atomic
    def _evaluar_reglas(cls, reglas, objeto, contexto):
        resultados = []
        for regla in reglas:
            cumplida = cls._evaluar_condiciones(regla.condiciones, contexto)
            resultado_texto = ""
            if cumplida:
                resultado_texto = cls._ejecutar_accion(regla, objeto, contexto)

            EjecucionRegla.objects.create(
                regla=regla, objeto_tipo=objeto.__class__.__name__, objeto_id=str(objeto.pk),
                condicion_cumplida=cumplida, accion_ejecutada=cumplida,
                contexto_evaluado=contexto, resultado=resultado_texto,
            )
            regla.ultima_ejecucion = timezone.now()
            regla.save(update_fields=["ultima_ejecucion"])

            resultados.append({"regla": regla.nombre, "cumplida": cumplida, "resultado": resultado_texto})
        return resultados

    @classmethod
    def evaluar_producto(cls, producto, solo_periodicas=False):
        reglas = ReglaAutomatizacion.objects.filter(
            empresa=producto.empresa, tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PRODUCTO, active=True,
        )
        if solo_periodicas:
            reglas = reglas.filter(evaluar_en=ReglaAutomatizacion.EVALUAR_PERIODICO)
        else:
            reglas = reglas.filter(evaluar_en=ReglaAutomatizacion.EVALUAR_AL_GUARDAR)

        contexto = cls._construir_contexto_producto(producto)
        return cls._evaluar_reglas(reglas, producto, contexto)

    @classmethod
    def evaluar_pedido_web(cls, pedido):
        reglas = ReglaAutomatizacion.objects.filter(
            empresa=pedido.empresa, tipo_entidad=ReglaAutomatizacion.TIPO_ENTIDAD_PEDIDO_WEB,
            active=True, evaluar_en=ReglaAutomatizacion.EVALUAR_AL_GUARDAR,
        )
        contexto = cls._construir_contexto_pedido_web(pedido)
        return cls._evaluar_reglas(reglas, pedido, contexto)

    @classmethod
    def evaluar_periodicas_de_empresa(cls, empresa):
        """Llamado por la tarea de Celery Beat: evalúa todas las reglas PERIODICO de tipo PRODUCTO de la empresa."""
        from apps.products.models import Producto

        resultados = []
        for producto in Producto.objects.filter(empresa=empresa, active=True, tipo=Producto.TIPO_PRODUCTO):
            resultados.extend(cls.evaluar_producto(producto, solo_periodicas=True))
        return resultados
