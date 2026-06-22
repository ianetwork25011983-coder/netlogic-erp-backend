from decimal import Decimal

import pytest

from apps.purchases.models import OrdenCompra, OrdenCompraItem
from apps.purchases.services import PurchaseError, PurchaseService


@pytest.mark.django_db
class TestRecepcionCompra:
    def test_recepcion_total_actualiza_estado_y_genera_entrada_inventario(self, empresa, sucursal, deposito, producto, proveedor, user, pyg):
        orden = OrdenCompra.objects.create(
            empresa=empresa, sucursal=sucursal, proveedor=proveedor,
            numero=PurchaseService.generar_numero_orden_compra(empresa), moneda=pyg, usuario=user,
        )
        item = OrdenCompraItem.objects.create(orden_compra=orden, producto=producto, cantidad=Decimal("10"), precio_unitario=Decimal("50000"))

        PurchaseService.recibir_orden(
            orden_compra=orden, deposito=deposito,
            items_data=[{"orden_compra_item_id": item.id, "cantidad_recibida": Decimal("10")}],
            usuario=user,
        )

        orden.refresh_from_db()
        assert orden.estado == OrdenCompra.ESTADO_RECIBIDA_TOTAL
        balance = producto.saldos.get(deposito=deposito, lote=None)
        assert balance.cantidad == Decimal("10")
        assert balance.costo_promedio_pyg == Decimal("50000.000000")

    def test_recepcion_parcial_actualiza_estado_correctamente(self, empresa, sucursal, deposito, producto, proveedor, user, pyg):
        orden = OrdenCompra.objects.create(
            empresa=empresa, sucursal=sucursal, proveedor=proveedor,
            numero=PurchaseService.generar_numero_orden_compra(empresa), moneda=pyg, usuario=user,
        )
        item = OrdenCompraItem.objects.create(orden_compra=orden, producto=producto, cantidad=Decimal("10"), precio_unitario=Decimal("50000"))

        PurchaseService.recibir_orden(
            orden_compra=orden, deposito=deposito,
            items_data=[{"orden_compra_item_id": item.id, "cantidad_recibida": Decimal("4")}],
            usuario=user,
        )
        orden.refresh_from_db()
        assert orden.estado == OrdenCompra.ESTADO_RECIBIDA_PARCIAL

    def test_no_se_puede_recibir_mas_de_lo_pedido(self, empresa, sucursal, deposito, producto, proveedor, user, pyg):
        orden = OrdenCompra.objects.create(
            empresa=empresa, sucursal=sucursal, proveedor=proveedor,
            numero=PurchaseService.generar_numero_orden_compra(empresa), moneda=pyg, usuario=user,
        )
        item = OrdenCompraItem.objects.create(orden_compra=orden, producto=producto, cantidad=Decimal("10"), precio_unitario=Decimal("50000"))

        with pytest.raises(PurchaseError):
            PurchaseService.recibir_orden(
                orden_compra=orden, deposito=deposito,
                items_data=[{"orden_compra_item_id": item.id, "cantidad_recibida": Decimal("999")}],
                usuario=user,
            )

    def test_no_se_puede_recibir_orden_cancelada(self, empresa, sucursal, deposito, producto, proveedor, user, pyg):
        orden = OrdenCompra.objects.create(
            empresa=empresa, sucursal=sucursal, proveedor=proveedor,
            numero=PurchaseService.generar_numero_orden_compra(empresa), moneda=pyg, usuario=user,
            estado=OrdenCompra.ESTADO_CANCELADA,
        )
        item = OrdenCompraItem.objects.create(orden_compra=orden, producto=producto, cantidad=Decimal("10"), precio_unitario=Decimal("50000"))

        with pytest.raises(PurchaseError):
            PurchaseService.recibir_orden(
                orden_compra=orden, deposito=deposito,
                items_data=[{"orden_compra_item_id": item.id, "cantidad_recibida": Decimal("1")}],
                usuario=user,
            )


@pytest.mark.django_db
class TestCompararCotizaciones:
    def test_compara_por_total_ascendente(self, empresa, sucursal, producto, proveedor, user, pyg):
        from apps.purchases.models import Cotizacion, CotizacionItem, SolicitudCompra

        solicitud = SolicitudCompra.objects.create(empresa=empresa, sucursal=sucursal, numero="SOL-001", solicitante=user)

        cot_cara = Cotizacion.objects.create(empresa=empresa, solicitud=solicitud, proveedor=proveedor, moneda=pyg, estado=Cotizacion.ESTADO_RECIBIDA)
        CotizacionItem.objects.create(cotizacion=cot_cara, producto=producto, cantidad=Decimal("10"), precio_unitario=Decimal("100000"))

        cot_barata = Cotizacion.objects.create(empresa=empresa, solicitud=solicitud, proveedor=proveedor, moneda=pyg, estado=Cotizacion.ESTADO_RECIBIDA)
        CotizacionItem.objects.create(cotizacion=cot_barata, producto=producto, cantidad=Decimal("10"), precio_unitario=Decimal("50000"))

        resultado = PurchaseService.comparar_cotizaciones(solicitud)
        assert resultado[0]["cotizacion_id"] == cot_barata.id
        assert resultado[1]["cotizacion_id"] == cot_cara.id
