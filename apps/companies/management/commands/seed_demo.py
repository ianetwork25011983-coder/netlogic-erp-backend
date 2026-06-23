"""
Carga datos de prueba para TODOS los modulos del ERP Netlogic.

Prerequisito: haber corrido seed_netlogic primero.

Uso:
    python manage.py seed_demo

Modulos cubiertos:
    - Pricing (listas de precios)
    - CRM (prospectos, etapas pipeline, oportunidades)
    - Compras (solicitudes, ordenes de compra)
    - Facturacion (facturas, presupuestos via BillingService)
    - Tesoreria (cajas, sesiones, movimientos)
"""
import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Carga datos demo para todos los modulos (requiere seed_netlogic previo)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seed Demo - Todos los modulos ==="))
        try:
            with transaction.atomic():
                self._load()
            self.stdout.write(self.style.SUCCESS("Demo cargado correctamente"))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Error: {exc}"))
            import traceback
            self.stderr.write(traceback.format_exc())
            raise

    def _load(self):
        self._empresa = self._get_empresa()
        self._sucursal = self._empresa.sucursales.filter(es_casa_matriz=True).first()
        self._admin = User.objects.filter(is_superuser=True).first()
        self._pyg = self._get_pyg()

        self._seed_pricing()
        self._seed_crm()
        self._seed_compras()
        self._seed_facturacion()
        self._seed_tesoreria()

    def _get_empresa(self):
        from apps.companies.models import Empresa
        emp = Empresa.objects.filter(ruc="80061234-5").first()
        if not emp:
            self.stdout.write(self.style.ERROR("Empresa Netlogic no encontrada. Correr seed_netlogic primero."))
            raise RuntimeError("Empresa no encontrada")
        return emp

    def _get_pyg(self):
        from apps.currencies.models import Currency
        return Currency.objects.get(code="PYG")

    # ──────────────────────────────────────────────────────────────────────────
    # PRICING
    # ──────────────────────────────────────────────────────────────────────────
    def _seed_pricing(self):
        from apps.pricing.models import ListaPrecio, PrecioProducto
        from apps.products.models import Producto

        lista_min, _ = ListaPrecio.objects.get_or_create(
            empresa=self._empresa, nombre="Lista Minorista",
            defaults=dict(moneda=self._pyg, es_default=True),
        )
        lista_may, _ = ListaPrecio.objects.get_or_create(
            empresa=self._empresa, nombre="Lista Mayorista",
            defaults=dict(moneda=self._pyg, es_default=False),
        )
        self._lista_precio = lista_min

        # Precio mayorista = 85% del precio minorista (descuento 15%)
        productos = Producto.objects.filter(empresa=self._empresa, active=True)
        pp_creados = 0
        for prod in productos:
            PrecioProducto.objects.get_or_create(
                lista_precio=lista_min, producto=prod,
                defaults=dict(precio=prod.precio),
            )
            precio_may = (prod.precio * Decimal("0.85")).quantize(Decimal("1"))
            PrecioProducto.objects.get_or_create(
                lista_precio=lista_may, producto=prod,
                defaults=dict(precio=precio_may),
            )
            pp_creados += 1

        self.stdout.write(f"  [OK] Pricing: 2 listas, {pp_creados * 2} precios")

    # ──────────────────────────────────────────────────────────────────────────
    # CRM
    # ──────────────────────────────────────────────────────────────────────────
    def _seed_crm(self):
        from apps.crm.models import Prospecto, EtapaPipeline, Oportunidad
        from apps.customers.models import Cliente

        # Etapas del pipeline de ventas
        etapas_data = [
            (1, "Primer Contacto", False, False),
            (2, "Calificacion", False, False),
            (3, "Propuesta Enviada", False, False),
            (4, "Negociacion", False, False),
            (5, "Ganado", True, False),
            (6, "Perdido", False, True),
        ]
        etapas = {}
        for orden, nombre, ganada, perdida in etapas_data:
            e, _ = EtapaPipeline.objects.get_or_create(
                empresa=self._empresa, orden=orden,
                defaults=dict(nombre=nombre, es_ganada=ganada, es_perdida=perdida),
            )
            etapas[nombre] = e
        self.stdout.write(f"  [OK] CRM: {len(etapas)} etapas pipeline")

        # Prospectos
        prospectos_data = [
            ("Constructora San Blas S.R.L.", "San Blas",  "Arq. Mario Zelaya", "0981-600-100", "mzelaya@sanblas.com.py", "Referido"),
            ("Distribuidora Norte S.A.",     "Dist. Norte","Lic. Sandra Ruiz",  "0991-700-200", "sruiz@distnorte.com.py", "Web"),
            ("Clinica Santa Ana",            "Sta. Ana",   "Dr. Pedro Meza",    "021-500-600",  "pmeza@santaana.com.py",  "Llamada fria"),
            ("Granja Familiar Aguape",       "Aguape",     "Ing. Luis Torres",  "0981-800-300", "ltorres@aguape.com.py",  "Feria Expo"),
            ("Municipalidad de Luque",       "Muni Luque", "Ing. Ana Flores",   "0221-432-100", "licitaciones@luque.gov.py", "Web"),
        ]
        prospectos_creados = []
        for razon, nombre, contacto, tel, email, origen in prospectos_data:
            p, created = Prospecto.objects.get_or_create(
                empresa=self._empresa, razon_social=razon,
                defaults=dict(
                    nombre_comercial=nombre, contacto_nombre=contacto,
                    telefono=tel, email=email, origen=origen,
                    estado="CALIFICADO", responsable=self._admin,
                ),
            )
            prospectos_creados.append(p)
        self.stdout.write(f"  [OK] CRM: {len(prospectos_creados)} prospectos")

        # Oportunidades sobre clientes existentes
        clientes = list(Cliente.objects.filter(empresa=self._empresa)[:5])
        opps_data = [
            (clientes[0], "Renovacion equipos informaticos Banco Regional",
             Decimal("45000000"), "Propuesta Enviada", 65, "2026-08-31"),
            (clientes[1], "Cableado estructurado edificio nueva sede",
             Decimal("18500000"), "Negociacion", 80, "2026-07-31"),
            (clientes[2], "Equipamiento sala de servidores",
             Decimal("32000000"), "Primer Contacto", 20, "2026-09-30"),
            (clientes[3], "Licenciamiento Microsoft 365 para 50 usuarios",
             Decimal("6500000"), "Calificacion", 50, "2026-07-15"),
            (clientes[4], "Instalacion red WiFi sucursales",
             Decimal("12000000"), "Propuesta Enviada", 60, "2026-08-15"),
        ]
        for cliente, nombre, valor, etapa_nombre, prob, fecha_cierre in opps_data:
            Oportunidad.objects.get_or_create(
                empresa=self._empresa,
                nombre=nombre,
                defaults=dict(
                    cliente=cliente,
                    etapa_pipeline=etapas[etapa_nombre],
                    valor_estimado=valor,
                    moneda=self._pyg,
                    probabilidad_porcentaje=Decimal(str(prob)),
                    fecha_cierre_estimada=datetime.date.fromisoformat(fecha_cierre),
                    responsable=self._admin,
                    estado="ABIERTA",
                ),
            )

        # Oportunidades sobre prospectos
        opps_prospectos = [
            (prospectos_creados[0], "Equipamiento PC area obras",
             Decimal("8500000"), "Calificacion", 40, "2026-09-30"),
            (prospectos_creados[2], "Infraestructura TI clinica",
             Decimal("22000000"), "Propuesta Enviada", 55, "2026-08-20"),
        ]
        for prospecto, nombre, valor, etapa_nombre, prob, fecha_cierre in opps_prospectos:
            Oportunidad.objects.get_or_create(
                empresa=self._empresa,
                nombre=nombre,
                defaults=dict(
                    prospecto=prospecto,
                    etapa_pipeline=etapas[etapa_nombre],
                    valor_estimado=valor,
                    moneda=self._pyg,
                    probabilidad_porcentaje=Decimal(str(prob)),
                    fecha_cierre_estimada=datetime.date.fromisoformat(fecha_cierre),
                    responsable=self._admin,
                    estado="ABIERTA",
                ),
            )

        total_opps = len(opps_data) + len(opps_prospectos)
        self.stdout.write(f"  [OK] CRM: {total_opps} oportunidades")

    # ──────────────────────────────────────────────────────────────────────────
    # COMPRAS
    # ──────────────────────────────────────────────────────────────────────────
    def _seed_compras(self):
        from apps.purchases.models import (
            SolicitudCompra, SolicitudCompraItem,
            OrdenCompra, OrdenCompraItem,
        )
        from apps.suppliers.models import Proveedor
        from apps.products.models import Producto

        proveedores = list(Proveedor.objects.filter(empresa=self._empresa))
        if not proveedores:
            self.stdout.write("  [WARN] Sin proveedores, omitiendo compras")
            return

        prods = {p.codigo: p for p in Producto.objects.filter(empresa=self._empresa, active=True)}

        # Solicitudes de compra
        sc_data = [
            ("SC-2026-001", [("NB-HP-001", 5), ("MON-LG-024", 8), ("KBD-LG-001", 10)]),
            ("SC-2026-002", [("SWT-CS-024", 2), ("RTR-TP-001", 5), ("AP-TP-001", 3)]),
            ("SC-2026-003", [("RAM-KG-8GB", 15), ("SSD-KG-480", 10), ("USB-KG-064", 20)]),
        ]
        for numero, items in sc_data:
            sc, created = SolicitudCompra.objects.get_or_create(
                numero=numero,
                defaults=dict(
                    empresa=self._empresa, sucursal=self._sucursal,
                    solicitante=self._admin, estado="APROBADA",
                ),
            )
            if created:
                for codigo, qty in items:
                    if codigo in prods:
                        SolicitudCompraItem.objects.get_or_create(
                            solicitud=sc, producto=prods[codigo],
                            defaults=dict(cantidad=Decimal(str(qty))),
                        )
        self.stdout.write(f"  [OK] Compras: {len(sc_data)} solicitudes")

        # Ordenes de compra
        oc_data = [
            ("OC-2026-001", proveedores[0], "CONFIRMADA",
             [("NB-HP-001", 5, Decimal("3800000")), ("MON-LG-024", 8, Decimal("980000"))]),
            ("OC-2026-002", proveedores[2] if len(proveedores) > 2 else proveedores[0], "ENVIADA",
             [("SWT-CS-024", 2, Decimal("1900000")), ("RTR-TP-001", 5, Decimal("280000"))]),
            ("OC-2026-003", proveedores[1] if len(proveedores) > 1 else proveedores[0], "RECIBIDA_TOTAL",
             [("RAM-KG-8GB", 15, Decimal("210000")), ("SSD-KG-480", 10, Decimal("320000")), ("USB-KG-064", 20, Decimal("58000"))]),
        ]
        for numero, proveedor, estado, items in oc_data:
            oc, created = OrdenCompra.objects.get_or_create(
                numero=numero,
                defaults=dict(
                    empresa=self._empresa, sucursal=self._sucursal,
                    proveedor=proveedor, moneda=self._pyg,
                    estado=estado, solicitante=self._admin,
                    fecha_entrega_estimada=datetime.date.today() + datetime.timedelta(days=7),
                ),
            )
            if created:
                for codigo, qty, precio in items:
                    if codigo in prods:
                        OrdenCompraItem.objects.get_or_create(
                            orden=oc, producto=prods[codigo],
                            defaults=dict(
                                cantidad=Decimal(str(qty)),
                                precio_unitario=precio,
                                cantidad_recibida=Decimal(str(qty)) if estado == "RECIBIDA_TOTAL" else Decimal("0"),
                            ),
                        )
        self.stdout.write(f"  [OK] Compras: {len(oc_data)} ordenes de compra")

    # ──────────────────────────────────────────────────────────────────────────
    # FACTURACION
    # ──────────────────────────────────────────────────────────────────────────
    def _seed_facturacion(self):
        from apps.billing.services import BillingService
        from apps.billing.models import DocumentoVenta
        from apps.companies.models import PuntoVenta, Deposito
        from apps.customers.models import Cliente
        from apps.products.models import Producto

        pv = PuntoVenta.objects.filter(sucursal=self._sucursal, active=True).first()
        deposito = Deposito.objects.filter(sucursal=self._sucursal, tipo="ALMACEN", active=True).first()

        if not pv or not deposito:
            self.stdout.write("  [WARN] Sin PuntoVenta o Deposito, omitiendo facturacion")
            return

        clientes = list(Cliente.objects.filter(empresa=self._empresa, active=True))
        prods = list(Producto.objects.filter(empresa=self._empresa, active=True, tipo="PRODUCTO"))

        if not clientes or not prods:
            self.stdout.write("  [WARN] Sin clientes o productos, omitiendo facturacion")
            return

        # Verificar que ya exista inventario en el deposito
        from apps.inventory.models import StockBalance
        tiene_stock = StockBalance.objects.filter(
            deposito=deposito, cantidad__gt=0, producto__empresa=self._empresa
        ).exists()

        if not tiene_stock:
            self.stdout.write("  [WARN] Sin stock en deposito, omitiendo facturas con inventario")
            return

        # Verificar si ya hay documentos
        ya_hay = DocumentoVenta.objects.filter(empresa=self._empresa).count()
        if ya_hay >= 8:
            self.stdout.write(f"  [OK] Facturacion: ya existen {ya_hay} documentos (omitiendo)")
            return

        # Facturas de venta
        ventas = [
            # (cliente_idx, tipo, condicion, afecta_inv, [(prod_idx, qty, precio)])
            (0, "FACTURA", "CONTADO", True,  [(0, 2, None), (5, 1, None)]),
            (1, "FACTURA", "CREDITO", False, [(1, 1, None), (7, 2, None)]),
            (2, "FACTURA", "CONTADO", True,  [(2, 3, None), (10, 5, None)]),
            (3, "PRESUPUESTO", "CONTADO", False, [(3, 1, None), (4, 2, None)]),
            (4, "FACTURA", "CONTADO", True,  [(6, 1, None), (11, 2, None)]),
            (0, "PRESUPUESTO", "CONTADO", False, [(8, 10, None), (9, 4, None)]),
            (2, "FACTURA", "CONTADO", True,  [(12, 2, None), (13, 1, None)]),
            (3, "FACTURA", "CREDITO", False, [(0, 1, None), (7, 3, None)]),
        ]

        emitidos = 0
        for cli_idx, tipo, condicion, afecta, items_raw in ventas:
            cliente = clientes[cli_idx % len(clientes)]
            items_data = []
            deposito_salida = None

            for prod_idx, qty, precio_override in items_raw:
                prod = prods[prod_idx % len(prods)]
                precio = precio_override or prod.precio

                # Verificar stock si afecta inventario
                if afecta and prod.descuenta_stock:
                    saldo = StockBalance.objects.filter(
                        producto=prod, deposito=deposito, cantidad__gte=qty
                    ).first()
                    if not saldo:
                        afecta = False  # No hay stock suficiente, emitir sin afectar inventario

                items_data.append({
                    "producto_id": prod.id,
                    "cantidad": Decimal(str(qty)),
                    "precio_unitario": precio,
                    "descuento_porcentaje": Decimal("0"),
                })

            if afecta:
                deposito_salida = deposito

            try:
                BillingService.emitir_documento(
                    empresa=self._empresa,
                    sucursal=self._sucursal,
                    punto_venta=pv,
                    tipo_documento=tipo,
                    cliente=cliente,
                    moneda_code="PYG",
                    items_data=items_data,
                    usuario=self._admin,
                    condicion_venta=condicion,
                    afecta_inventario=bool(deposito_salida),
                    deposito_salida=deposito_salida,
                    observaciones="Datos de prueba generados por seed_demo",
                )
                emitidos += 1
            except Exception as exc:
                self.stdout.write(f"  [WARN] Error emitiendo {tipo}: {exc}")

        self.stdout.write(f"  [OK] Facturacion: {emitidos} documentos emitidos")

    # ──────────────────────────────────────────────────────────────────────────
    # TESORERIA
    # ──────────────────────────────────────────────────────────────────────────
    def _seed_tesoreria(self):
        from apps.treasury.models import Caja, AperturaCaja, MovimientoCaja
        from apps.treasury.services import TreasuryService

        cajas = list(Caja.objects.filter(empresa=self._empresa, active=True))
        if not cajas:
            self.stdout.write("  [WARN] Sin cajas, omitiendo tesoreria")
            return

        # Verificar si ya hay una sesion abierta
        sesion_abierta = AperturaCaja.objects.filter(
            caja__empresa=self._empresa, estado="ABIERTA"
        ).first()

        if sesion_abierta:
            self.stdout.write(f"  [OK] Tesoreria: sesion ya abierta (Apertura #{sesion_abierta.id})")
            self._apertura = sesion_abierta
        else:
            caja = cajas[0]
            try:
                apertura = TreasuryService.abrir_caja(
                    caja, self._admin,
                    monto_inicial=Decimal("500000"),
                    moneda=self._pyg,
                    observaciones="Apertura inicial seed demo",
                )
                self._apertura = apertura
                self.stdout.write(f"  [OK] Tesoreria: caja abierta con Gs. 500.000")
            except Exception as exc:
                self.stdout.write(f"  [WARN] No se pudo abrir caja: {exc}")
                return

        apertura = self._apertura

        # Registrar algunos movimientos manuales
        movimientos_data = [
            ("INGRESO", "OTRO", "EFECTIVO", Decimal("200000"), "Cobro servicio mantenimiento PC"),
            ("EGRESO",  "GASTO", "EFECTIVO", Decimal("85000"),  "Compra suministros de oficina"),
            ("INGRESO", "OTRO", "QR",        Decimal("350000"), "Cobro servicio instalacion red"),
            ("EGRESO",  "RETIRO", "EFECTIVO", Decimal("150000"), "Retiro de efectivo"),
            ("INGRESO", "COBRO_FACTURA", "TRANSFERENCIA", Decimal("4500000"), "Cobro factura Banco Regional"),
        ]

        ya_hay_mov = MovimientoCaja.objects.filter(apertura_caja=apertura).count()
        if ya_hay_mov >= 3:
            self.stdout.write(f"  [OK] Tesoreria: ya existen {ya_hay_mov} movimientos (omitiendo)")
            return

        mov_creados = 0
        for tipo, concepto, medio, monto, obs in movimientos_data:
            try:
                TreasuryService.registrar_movimiento(
                    apertura_caja=apertura,
                    tipo=tipo,
                    concepto=concepto,
                    medio_pago=medio,
                    monto=monto,
                    moneda=self._pyg,
                    usuario=self._admin,
                    observaciones=obs,
                )
                mov_creados += 1
            except Exception as exc:
                self.stdout.write(f"  [WARN] Error movimiento {tipo}: {exc}")

        self.stdout.write(f"  [OK] Tesoreria: {mov_creados} movimientos registrados")
