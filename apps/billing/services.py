"""
Motor de Facturación (Módulo 10).

`BillingService.emitir_documento()` es el único punto de entrada para
crear un Factura/NC/ND/Presupuesto/Remisión. Calcula subtotales e
impuesto por línea, snapshotea la tasa de cambio del día vía
`CurrencyService`, genera la numeración fiscal correlativa por punto de
venta, y si `afecta_inventario=True` llama a `InventoryService` (salida
para Factura/Remisión, entrada para Nota de Crédito que implica
devolución de mercadería).
"""
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction

from apps.currencies.services import CurrencyService
from apps.inventory.services import InventoryError, InventoryService

from .models import DocumentoVenta, DocumentoVentaItem, SecuenciaDocumento

CENTS = Decimal("0.01")


class BillingError(Exception):
    pass


class BillingService:
    # ------------------------------------------------------------------
    # Numeración fiscal correlativa por punto de venta + tipo de documento
    # ------------------------------------------------------------------
    @staticmethod
    @transaction.atomic
    def generar_numero(punto_venta, tipo_documento):
        secuencia, _ = SecuenciaDocumento.objects.select_for_update().get_or_create(
            punto_venta=punto_venta, tipo_documento=tipo_documento
        )
        secuencia.ultimo_numero += 1
        secuencia.save(update_fields=["ultimo_numero"])
        return f"{punto_venta.establecimiento}-{punto_venta.punto_expedicion}-{secuencia.ultimo_numero:07d}"

    # ------------------------------------------------------------------
    # Cálculo de totales por línea
    # ------------------------------------------------------------------
    @staticmethod
    def _calcular_linea(cantidad, precio_unitario, descuento_porcentaje, tasa_impuesto):
        subtotal = Decimal(cantidad) * Decimal(precio_unitario) * (1 - Decimal(descuento_porcentaje) / 100)
        impuesto = subtotal * Decimal(tasa_impuesto) / 100
        subtotal_q = subtotal.quantize(CENTS, rounding=ROUND_HALF_UP)
        impuesto_q = impuesto.quantize(CENTS, rounding=ROUND_HALF_UP)
        return subtotal_q, impuesto_q, subtotal_q + impuesto_q

    # ------------------------------------------------------------------
    # Emisión de documento
    # ------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def emitir_documento(
        cls, *, empresa, sucursal, punto_venta, tipo_documento, cliente, moneda_code, items_data, usuario,
        condicion_venta=DocumentoVenta.CONDICION_CONTADO, fecha_emision=None, fecha_vencimiento=None,
        documento_referencia=None, afecta_inventario=False, deposito_salida=None, observaciones="",
        descuento_global=None,
    ):
        """
        `items_data`: lista de dicts {"producto_id", "cantidad",
        "precio_unitario", "descuento_porcentaje" opcional, "impuesto_id" opcional}.
        Si `impuesto_id` no se indica, se usa el impuesto configurado en el producto.

        `descuento_global`: descuento adicional a nivel de documento (ej. el
        descuento de un cupón aplicado en Pedidos Web), restado del total
        después de impuestos. No se redistribuye entre líneas ni recalcula
        el IVA por línea — es una simplificación deliberada, documentada en el README.
        """
        import datetime

        from apps.currencies.models import Currency
        from apps.products.models import Producto

        fecha_emision = fecha_emision or datetime.date.today()

        if afecta_inventario and deposito_salida is None:
            raise BillingError("Si el documento afecta inventario, debe indicar el depósito de salida.")
        if tipo_documento in (DocumentoVenta.TIPO_NOTA_CREDITO, DocumentoVenta.TIPO_NOTA_DEBITO) and documento_referencia is None:
            raise BillingError("Una Nota de Crédito/Débito debe referenciar la factura que afecta.")

        moneda = Currency.objects.get(code=moneda_code)
        tipo_cambio_pyg = CurrencyService.get_rate(moneda_code, fecha_emision)
        numero = cls.generar_numero(punto_venta, tipo_documento)

        documento = DocumentoVenta.objects.create(
            empresa=empresa, sucursal=sucursal, punto_venta=punto_venta, tipo_documento=tipo_documento,
            numero=numero, cliente=cliente, documento_referencia=documento_referencia, moneda=moneda,
            condicion_venta=condicion_venta, estado=DocumentoVenta.ESTADO_BORRADOR,
            afecta_inventario=afecta_inventario, deposito_salida=deposito_salida,
            fecha_emision=fecha_emision, fecha_vencimiento=fecha_vencimiento,
            observaciones=observaciones, usuario=usuario, tipo_cambio_pyg=tipo_cambio_pyg,
        )

        subtotal_doc = Decimal("0")
        impuesto_doc = Decimal("0")

        es_entrada_stock = tipo_documento == DocumentoVenta.TIPO_NOTA_CREDITO
        es_salida_stock = tipo_documento in (DocumentoVenta.TIPO_FACTURA, DocumentoVenta.TIPO_REMISION)

        for item_data in items_data:
            producto = Producto.objects.get(pk=item_data["producto_id"])
            cantidad = Decimal(item_data["cantidad"])
            precio_unitario = Decimal(item_data["precio_unitario"])
            descuento = Decimal(item_data.get("descuento_porcentaje", 0))

            impuesto_id = item_data.get("impuesto_id")
            impuesto_obj = producto.impuesto
            if impuesto_id:
                from apps.products.models import Impuesto

                impuesto_obj = Impuesto.objects.get(pk=impuesto_id)
            tasa = impuesto_obj.tasa_porcentaje if impuesto_obj else Decimal("0")

            subtotal_linea, impuesto_linea, total_linea = cls._calcular_linea(cantidad, precio_unitario, descuento, tasa)
            subtotal_doc += subtotal_linea
            impuesto_doc += impuesto_linea

            movimiento = None
            if afecta_inventario and producto.descuenta_stock:
                try:
                    if es_salida_stock:
                        movimiento = InventoryService.registrar_salida(
                            producto=producto, deposito=deposito_salida, cantidad=cantidad, usuario=usuario,
                            documento_tipo=tipo_documento, documento_referencia=numero,
                        )
                    elif es_entrada_stock:
                        balance = producto.saldos.filter(deposito=deposito_salida, lote=None).first()
                        costo_unitario_pyg = balance.costo_promedio_pyg if balance else Decimal("0")
                        movimiento = InventoryService.registrar_entrada(
                            producto=producto, deposito=deposito_salida, cantidad=cantidad,
                            costo_unitario=costo_unitario_pyg, moneda_costo_code="PYG", usuario=usuario,
                            documento_tipo=tipo_documento, documento_referencia=numero,
                        )
                except InventoryError as exc:
                    raise BillingError(str(exc)) from exc

            DocumentoVentaItem.objects.create(
                documento=documento, producto=producto, descripcion=producto.nombre,
                cantidad=cantidad, precio_unitario=precio_unitario, descuento_porcentaje=descuento,
                impuesto=impuesto_obj, tasa_impuesto_aplicada=tasa,
                subtotal_linea=subtotal_linea, impuesto_linea=impuesto_linea, total_linea=total_linea,
                movimiento_inventario=movimiento,
            )

        total_doc = subtotal_doc + impuesto_doc
        descuento_global = Decimal(descuento_global) if descuento_global else Decimal("0")
        if descuento_global > total_doc:
            raise BillingError("El descuento global no puede superar el total del documento.")
        total_doc -= descuento_global
        total_pyg = (total_doc * tipo_cambio_pyg).quantize(CENTS, rounding=ROUND_HALF_UP)

        documento.subtotal = subtotal_doc
        documento.impuesto_total = impuesto_doc
        documento.descuento_global = descuento_global
        documento.total = total_doc
        documento.total_pyg = total_pyg
        documento.estado = DocumentoVenta.ESTADO_EMITIDA
        if tipo_documento == DocumentoVenta.TIPO_FACTURA:
            documento.saldo_pendiente = total_doc
        documento.save()

        return documento

    # ------------------------------------------------------------------
    # Conversión Presupuesto -> Factura
    # ------------------------------------------------------------------
    @classmethod
    def convertir_presupuesto_a_factura(
        cls, presupuesto, *, punto_venta, usuario, afecta_inventario=True,
        deposito_salida=None, condicion_venta=DocumentoVenta.CONDICION_CONTADO,
    ):
        if presupuesto.tipo_documento != DocumentoVenta.TIPO_PRESUPUESTO:
            raise BillingError("Solo se puede convertir un documento de tipo PRESUPUESTO.")

        items_data = [
            {
                "producto_id": item.producto_id,
                "cantidad": item.cantidad,
                "precio_unitario": item.precio_unitario,
                "descuento_porcentaje": item.descuento_porcentaje,
                "impuesto_id": item.impuesto_id,
            }
            for item in presupuesto.items.all()
        ]
        return cls.emitir_documento(
            empresa=presupuesto.empresa, sucursal=presupuesto.sucursal, punto_venta=punto_venta,
            tipo_documento=DocumentoVenta.TIPO_FACTURA, cliente=presupuesto.cliente,
            moneda_code=presupuesto.moneda.code, items_data=items_data, usuario=usuario,
            condicion_venta=condicion_venta, documento_referencia=presupuesto,
            afecta_inventario=afecta_inventario, deposito_salida=deposito_salida,
        )

    # ------------------------------------------------------------------
    # Anulación
    # ------------------------------------------------------------------
    @classmethod
    @transaction.atomic
    def anular_documento(cls, documento, motivo, usuario):
        if documento.estado == DocumentoVenta.ESTADO_ANULADA:
            raise BillingError("El documento ya está anulado.")

        if documento.afecta_inventario:
            for item in documento.items.select_related("producto").all():
                if not item.producto.descuenta_stock:
                    continue
                try:
                    if documento.tipo_documento in (DocumentoVenta.TIPO_FACTURA, DocumentoVenta.TIPO_REMISION):
                        # Se había hecho una SALIDA: para anular, se repone con una ENTRADA al mismo costo.
                        costo = item.movimiento_inventario.costo_unitario_pyg if item.movimiento_inventario else Decimal("0")
                        InventoryService.registrar_entrada(
                            producto=item.producto, deposito=documento.deposito_salida, cantidad=item.cantidad,
                            costo_unitario=costo, moneda_costo_code="PYG", usuario=usuario,
                            documento_tipo="ANULACION", documento_referencia=documento.numero,
                            observaciones=f"Reverso por anulación de {documento.numero}: {motivo}",
                        )
                    elif documento.tipo_documento == DocumentoVenta.TIPO_NOTA_CREDITO:
                        # Se había hecho una ENTRADA: para anular, se descuenta con una SALIDA.
                        InventoryService.registrar_salida(
                            producto=item.producto, deposito=documento.deposito_salida, cantidad=item.cantidad,
                            usuario=usuario, documento_tipo="ANULACION", documento_referencia=documento.numero,
                            observaciones=f"Reverso por anulación de {documento.numero}: {motivo}",
                        )
                except InventoryError as exc:
                    raise BillingError(str(exc)) from exc

        documento.estado = DocumentoVenta.ESTADO_ANULADA
        documento.saldo_pendiente = Decimal("0")
        documento.observaciones = f"{documento.observaciones}\n[ANULADA] {motivo}".strip()
        documento.save(update_fields=["estado", "saldo_pendiente", "observaciones"])
        return documento
