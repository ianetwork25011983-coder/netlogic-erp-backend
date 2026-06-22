"""
Motor de inventario (Módulo 4).

Todo el resto del ERP (Compras, Ventas, Pedidos Web) debe registrar
movimientos de stock exclusivamente a través de `InventoryService`, nunca
escribiendo directo en `StockBalance` o `MovimientoInventario`. Esto
garantiza que el Kardex, las capas de costo y los saldos se mantengan
consistentes sin duplicar la lógica de costeo en cada módulo.
"""
import uuid
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.currencies.services import CurrencyService

from .models import CapaCosto, MovimientoInventario, StockBalance, StockReserva

PYG_QUANTIZE = Decimal("1")
COST_QUANTIZE = Decimal("0.000001")


class InventoryError(Exception):
    pass


class InsufficientStockError(InventoryError):
    def __init__(self, producto, deposito, disponible, solicitado):
        self.producto = producto
        self.deposito = deposito
        self.disponible = disponible
        self.solicitado = solicitado
        super().__init__(
            f"Stock insuficiente de {producto.codigo} en {deposito}: "
            f"disponible {disponible}, solicitado {solicitado}."
        )


class ProductoNoDescuentaStockError(InventoryError):
    pass


def _round_pyg(value: Decimal) -> Decimal:
    return Decimal(value).quantize(PYG_QUANTIZE, rounding=ROUND_HALF_UP)


def _round_cost(value: Decimal) -> Decimal:
    return Decimal(value).quantize(COST_QUANTIZE, rounding=ROUND_HALF_UP)


class InventoryService:
    @staticmethod
    def _get_or_create_balance(producto, deposito, lote):
        balance, _ = StockBalance.objects.select_for_update().get_or_create(
            producto=producto, deposito=deposito, lote=lote,
        )
        return balance

    @classmethod
    def _aplicar_entrada_costo(cls, producto, deposito, lote, cantidad, costo_unitario_pyg, movimiento):
        """Actualiza StockBalance y, si corresponde, crea una CapaCosto nueva."""
        balance = cls._get_or_create_balance(producto, deposito, lote)

        valor_anterior = balance.cantidad * balance.costo_promedio_pyg
        nueva_cantidad = balance.cantidad + cantidad
        valor_nuevo = valor_anterior + (cantidad * costo_unitario_pyg)
        balance.costo_promedio_pyg = (
            _round_cost(valor_nuevo / nueva_cantidad) if nueva_cantidad > 0 else Decimal("0")
        )
        balance.cantidad = nueva_cantidad
        balance.save(update_fields=["cantidad", "costo_promedio_pyg", "updated_at"])

        if producto.metodo_costeo in (producto.METODO_FIFO, producto.METODO_LIFO):
            CapaCosto.objects.create(
                producto=producto,
                deposito=deposito,
                lote=lote,
                cantidad_original=cantidad,
                cantidad_disponible=cantidad,
                costo_unitario_pyg=costo_unitario_pyg,
                fecha_ingreso=movimiento.fecha or timezone.now(),
                movimiento_origen=movimiento,
            )
        return balance

    @classmethod
    def _calcular_costo_salida(cls, producto, deposito, lote, cantidad):
        """
        Determina el costo unitario a usar para una salida, según el
        método de costeo del producto, y descuenta de las capas FIFO/LIFO
        si corresponde. Devuelve (costo_unitario_pyg, costo_total_pyg).
        No modifica StockBalance.cantidad (eso lo hace el caller).
        """
        balance = cls._get_or_create_balance(producto, deposito, lote)

        if balance.cantidad < cantidad:
            raise InsufficientStockError(producto, deposito, balance.cantidad, cantidad)

        if producto.metodo_costeo == producto.METODO_PROMEDIO:
            costo_unitario = balance.costo_promedio_pyg
            costo_total = _round_pyg(costo_unitario * cantidad)
            return costo_unitario, costo_total

        # FIFO / LIFO: consumir capas en orden.
        orden = "fecha_ingreso" if producto.metodo_costeo == producto.METODO_FIFO else "-fecha_ingreso"
        capas = list(
            CapaCosto.objects.select_for_update()
            .filter(producto=producto, deposito=deposito, lote=lote, cantidad_disponible__gt=0)
            .order_by(orden)
        )

        restante = cantidad
        costo_total_acumulado = Decimal("0")
        for capa in capas:
            if restante <= 0:
                break
            consumir = min(capa.cantidad_disponible, restante)
            costo_total_acumulado += consumir * capa.costo_unitario_pyg
            capa.cantidad_disponible -= consumir
            capa.save(update_fields=["cantidad_disponible"])
            restante -= consumir

        if restante > 0:
            # No debería pasar si balance.cantidad estaba sincronizado con
            # las capas; lo tratamos como inconsistencia de datos.
            raise InsufficientStockError(producto, deposito, cantidad - restante, cantidad)

        costo_total = _round_pyg(costo_total_acumulado)
        costo_unitario = _round_cost(costo_total_acumulado / cantidad) if cantidad else Decimal("0")
        return costo_unitario, costo_total

    @classmethod
    def _crear_movimiento(
        cls, *, producto, deposito, tipo_movimiento, cantidad, costo_unitario_pyg, costo_total_pyg,
        balance_posterior, usuario, lote=None, ubicacion=None, grupo_transferencia=None,
        documento_tipo="", documento_referencia="", observaciones="",
    ):
        return MovimientoInventario.objects.create(
            producto=producto,
            deposito=deposito,
            lote=lote,
            ubicacion=ubicacion,
            tipo_movimiento=tipo_movimiento,
            cantidad=cantidad,
            costo_unitario_pyg=costo_unitario_pyg,
            costo_total_pyg=costo_total_pyg,
            saldo_cantidad_posterior=balance_posterior.cantidad,
            saldo_valor_posterior_pyg=_round_pyg(balance_posterior.valor_total_pyg),
            grupo_transferencia=grupo_transferencia,
            documento_tipo=documento_tipo,
            documento_referencia=documento_referencia,
            observaciones=observaciones,
            usuario=usuario,
        )

    # ------------------------------------------------------------------
    # API pública
    # ------------------------------------------------------------------

    @classmethod
    @transaction.atomic
    def registrar_entrada(
        cls, *, producto, deposito, cantidad, costo_unitario, moneda_costo_code, usuario,
        lote=None, ubicacion=None, documento_tipo="", documento_referencia="", observaciones="",
        fecha_valorizacion=None,
    ):
        if not producto.descuenta_stock:
            raise ProductoNoDescuentaStockError(
                f"{producto} es de tipo {producto.tipo} y no maneja stock."
            )

        costo_unitario_pyg = _round_cost(
            CurrencyService.convert_to_base(Decimal(costo_unitario), moneda_costo_code, fecha_valorizacion)
        )

        movimiento = cls._crear_movimiento(
            producto=producto, deposito=deposito, tipo_movimiento=MovimientoInventario.TIPO_ENTRADA,
            cantidad=cantidad, costo_unitario_pyg=costo_unitario_pyg,
            costo_total_pyg=_round_pyg(costo_unitario_pyg * cantidad),
            balance_posterior=StockBalance(cantidad=0, costo_promedio_pyg=0),  # placeholder, se corrige abajo
            usuario=usuario, lote=lote, ubicacion=ubicacion, documento_tipo=documento_tipo,
            documento_referencia=documento_referencia, observaciones=observaciones,
        )
        balance = cls._aplicar_entrada_costo(producto, deposito, lote, Decimal(cantidad), costo_unitario_pyg, movimiento)
        movimiento.saldo_cantidad_posterior = balance.cantidad
        movimiento.saldo_valor_posterior_pyg = _round_pyg(balance.valor_total_pyg)
        movimiento.save(update_fields=["saldo_cantidad_posterior", "saldo_valor_posterior_pyg"])
        return movimiento

    @classmethod
    @transaction.atomic
    def registrar_salida(
        cls, *, producto, deposito, cantidad, usuario, lote=None, ubicacion=None,
        documento_tipo="", documento_referencia="", observaciones="",
    ):
        if not producto.descuenta_stock:
            raise ProductoNoDescuentaStockError(
                f"{producto} es de tipo {producto.tipo} y no maneja stock."
            )

        cantidad = Decimal(cantidad)
        costo_unitario_pyg, costo_total_pyg = cls._calcular_costo_salida(producto, deposito, lote, cantidad)

        balance = cls._get_or_create_balance(producto, deposito, lote)
        balance.cantidad -= cantidad
        balance.save(update_fields=["cantidad", "updated_at"])

        return cls._crear_movimiento(
            producto=producto, deposito=deposito, tipo_movimiento=MovimientoInventario.TIPO_SALIDA,
            cantidad=cantidad, costo_unitario_pyg=costo_unitario_pyg, costo_total_pyg=costo_total_pyg,
            balance_posterior=balance, usuario=usuario, lote=lote, ubicacion=ubicacion,
            documento_tipo=documento_tipo, documento_referencia=documento_referencia,
            observaciones=observaciones,
        )

    @classmethod
    @transaction.atomic
    def registrar_transferencia(
        cls, *, producto, deposito_origen, deposito_destino, cantidad, usuario,
        lote=None, ubicacion_destino=None, documento_tipo="", documento_referencia="", observaciones="",
    ):
        if deposito_origen.pk == deposito_destino.pk:
            raise InventoryError("El depósito de origen y destino no pueden ser el mismo.")

        cantidad = Decimal(cantidad)
        grupo = uuid.uuid4()

        costo_unitario_pyg, costo_total_pyg = cls._calcular_costo_salida(producto, deposito_origen, lote, cantidad)

        balance_origen = cls._get_or_create_balance(producto, deposito_origen, lote)
        balance_origen.cantidad -= cantidad
        balance_origen.save(update_fields=["cantidad", "updated_at"])

        mov_salida = cls._crear_movimiento(
            producto=producto, deposito=deposito_origen, tipo_movimiento=MovimientoInventario.TIPO_TRANSFERENCIA_SALIDA,
            cantidad=cantidad, costo_unitario_pyg=costo_unitario_pyg, costo_total_pyg=costo_total_pyg,
            balance_posterior=balance_origen, usuario=usuario, lote=lote, grupo_transferencia=grupo,
            documento_tipo=documento_tipo, documento_referencia=documento_referencia, observaciones=observaciones,
        )

        # La entrada en destino se valoriza al MISMO costo que salió del
        # origen: una transferencia interna no genera ganancia ni pérdida.
        mov_entrada = cls._crear_movimiento(
            producto=producto, deposito=deposito_destino, tipo_movimiento=MovimientoInventario.TIPO_TRANSFERENCIA_ENTRADA,
            cantidad=cantidad, costo_unitario_pyg=costo_unitario_pyg, costo_total_pyg=costo_total_pyg,
            balance_posterior=StockBalance(cantidad=0, costo_promedio_pyg=0), usuario=usuario,
            lote=lote, ubicacion=ubicacion_destino, grupo_transferencia=grupo,
            documento_tipo=documento_tipo, documento_referencia=documento_referencia, observaciones=observaciones,
        )
        balance_destino = cls._aplicar_entrada_costo(producto, deposito_destino, lote, cantidad, costo_unitario_pyg, mov_entrada)
        mov_entrada.saldo_cantidad_posterior = balance_destino.cantidad
        mov_entrada.saldo_valor_posterior_pyg = _round_pyg(balance_destino.valor_total_pyg)
        mov_entrada.save(update_fields=["saldo_cantidad_posterior", "saldo_valor_posterior_pyg"])

        return mov_salida, mov_entrada

    @classmethod
    @transaction.atomic
    def registrar_ajuste(
        cls, *, producto, deposito, cantidad_ajuste, motivo, usuario, lote=None,
        costo_unitario_manual=None, moneda_costo_code=None, documento_referencia="",
    ):
        """
        `cantidad_ajuste` puede ser positivo (sobrante) o negativo (faltante).
        Si es positivo y no se indica costo manual, se usa el costo
        promedio actual del producto en ese depósito.
        """
        cantidad_ajuste = Decimal(cantidad_ajuste)
        if cantidad_ajuste == 0:
            raise InventoryError("La cantidad de ajuste no puede ser cero.")

        if cantidad_ajuste > 0:
            balance_actual = cls._get_or_create_balance(producto, deposito, lote)
            if costo_unitario_manual is not None and moneda_costo_code:
                costo_unitario_pyg = _round_cost(
                    CurrencyService.convert_to_base(Decimal(costo_unitario_manual), moneda_costo_code)
                )
            else:
                costo_unitario_pyg = balance_actual.costo_promedio_pyg

            movimiento = cls._crear_movimiento(
                producto=producto, deposito=deposito, tipo_movimiento=MovimientoInventario.TIPO_AJUSTE_POSITIVO,
                cantidad=cantidad_ajuste, costo_unitario_pyg=costo_unitario_pyg,
                costo_total_pyg=_round_pyg(costo_unitario_pyg * cantidad_ajuste),
                balance_posterior=StockBalance(cantidad=0, costo_promedio_pyg=0), usuario=usuario, lote=lote,
                documento_tipo="AJUSTE_MANUAL", documento_referencia=documento_referencia, observaciones=motivo,
            )
            balance = cls._aplicar_entrada_costo(producto, deposito, lote, cantidad_ajuste, costo_unitario_pyg, movimiento)
            movimiento.saldo_cantidad_posterior = balance.cantidad
            movimiento.saldo_valor_posterior_pyg = _round_pyg(balance.valor_total_pyg)
            movimiento.save(update_fields=["saldo_cantidad_posterior", "saldo_valor_posterior_pyg"])
            return movimiento

        cantidad_absoluta = abs(cantidad_ajuste)
        costo_unitario_pyg, costo_total_pyg = cls._calcular_costo_salida(producto, deposito, lote, cantidad_absoluta)
        balance = cls._get_or_create_balance(producto, deposito, lote)
        balance.cantidad -= cantidad_absoluta
        balance.save(update_fields=["cantidad", "updated_at"])

        return cls._crear_movimiento(
            producto=producto, deposito=deposito, tipo_movimiento=MovimientoInventario.TIPO_AJUSTE_NEGATIVO,
            cantidad=cantidad_absoluta, costo_unitario_pyg=costo_unitario_pyg, costo_total_pyg=costo_total_pyg,
            balance_posterior=balance, usuario=usuario, lote=lote,
            documento_tipo="AJUSTE_MANUAL", documento_referencia=documento_referencia, observaciones=motivo,
        )

    @classmethod
    @transaction.atomic
    def registrar_conteo_fisico(cls, *, producto, deposito, cantidad_contada, usuario, lote=None, documento_referencia=""):
        """
        Conteo cíclico / inventario físico: compara la cantidad contada
        contra el saldo del sistema y genera automáticamente el ajuste
        (positivo o negativo) por la diferencia. Si no hay diferencia,
        no genera ningún movimiento.
        """
        balance = cls._get_or_create_balance(producto, deposito, lote)
        diferencia = Decimal(cantidad_contada) - balance.cantidad

        if diferencia == 0:
            return None

        return cls.registrar_ajuste(
            producto=producto, deposito=deposito, cantidad_ajuste=diferencia,
            motivo=f"Ajuste por conteo físico/cíclico. Sistema: {balance.cantidad}, Contado: {cantidad_contada}.",
            usuario=usuario, lote=lote, documento_referencia=documento_referencia,
        )

    # ------------------------------------------------------------------
    # Reservas de stock (Módulo 8 - Pedidos Web)
    # ------------------------------------------------------------------
    @staticmethod
    def cantidad_disponible_venta(producto, deposito):
        """Saldo físico menos reservas activas = lo que realmente se puede vender."""
        from django.db.models import Sum

        balance = StockBalance.objects.filter(producto=producto, deposito=deposito, lote=None).first()
        cantidad_balance = balance.cantidad if balance else Decimal("0")
        reservado = StockReserva.objects.filter(
            producto=producto, deposito=deposito, active=True
        ).aggregate(total=Sum("cantidad"))["total"] or Decimal("0")
        return cantidad_balance - reservado

    @classmethod
    @transaction.atomic
    def reservar_stock(cls, *, producto, deposito, cantidad, referencia_tipo, referencia_id):
        cantidad = Decimal(cantidad)
        disponible = cls.cantidad_disponible_venta(producto, deposito)
        if disponible < cantidad:
            raise InsufficientStockError(producto, deposito, disponible, cantidad)

        return StockReserva.objects.create(
            producto=producto, deposito=deposito, cantidad=cantidad,
            referencia_tipo=referencia_tipo, referencia_id=str(referencia_id),
        )

    @staticmethod
    def liberar_reservas_de_referencia(referencia_tipo, referencia_id):
        """Libera todas las reservas activas de un pedido (al cancelar, rechazar o facturar)."""
        StockReserva.objects.filter(
            referencia_tipo=referencia_tipo, referencia_id=str(referencia_id), active=True
        ).update(active=False, released_at=timezone.now())

    # ------------------------------------------------------------------
    # Consultas / reportes
    # ------------------------------------------------------------------

    @staticmethod
    def get_kardex(producto, deposito=None, lote=None):
        qs = MovimientoInventario.objects.filter(producto=producto).select_related("deposito", "lote", "usuario")
        if deposito is not None:
            qs = qs.filter(deposito=deposito)
        if lote is not None:
            qs = qs.filter(lote=lote)
        return qs.order_by("fecha")

    @staticmethod
    def get_valorizacion(empresa=None, deposito=None, categoria=None):
        qs = StockBalance.objects.select_related("producto", "deposito").filter(cantidad__gt=0)
        if empresa is not None:
            qs = qs.filter(producto__empresa=empresa)
        if deposito is not None:
            qs = qs.filter(deposito=deposito)
        if categoria is not None:
            qs = qs.filter(producto__categoria=categoria)
        return qs
