"""
Carga datos de prueba para el tenant Netlogic.

Uso:
    python manage.py seed_netlogic
    python manage.py seed_netlogic --reset   # borra y recrea todo

Los datos son idempotentes: si ya existen (por codigo/RUC unico) se
omiten sin error. Asigna automaticamente al primer superusuario
encontrado a la empresa Netlogic.
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()


class Command(BaseCommand):
    help = "Carga datos de prueba para el tenant Netlogic"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Elimina datos existentes del tenant antes de recrearlos",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seed Netlogic ==="))
        try:
            with transaction.atomic():
                self._run(reset=options["reset"])
            self.stdout.write(self.style.SUCCESS("Datos cargados correctamente"))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Error: {exc}"))
            raise

    def _run(self, reset: bool):
        empresa = self._seed_base(reset)
        self._seed_clientes(empresa)
        self._seed_proveedores(empresa)
        self._seed_productos(empresa)
        self._seed_stock(empresa)
        self._seed_cajas(empresa)
        self._assign_superuser(empresa)

    # ------------------------------------------------------------------
    # 1. BASE
    # ------------------------------------------------------------------
    def _seed_base(self, reset):
        from apps.currencies.models import Currency, ExchangeRate
        from apps.companies.models import Empresa, Sucursal, Deposito, PuntoVenta

        pyg, _ = Currency.objects.get_or_create(
            code="PYG",
            defaults=dict(name="Guarani Paraguayo", symbol="Gs.", decimal_places=0, is_base=True),
        )
        usd, _ = Currency.objects.get_or_create(
            code="USD",
            defaults=dict(name="Dolar Estadounidense", symbol="$", decimal_places=2, is_base=False),
        )
        self.stdout.write("  [OK] Monedas: PYG, USD")

        ExchangeRate.objects.get_or_create(
            currency=usd,
            effective_date="2026-06-01",
            defaults=dict(rate_to_base=Decimal("7600"), source="MANUAL"),
        )
        self.stdout.write("  [OK] Tasa USD = 7600 PYG")

        empresa, created = Empresa.objects.get_or_create(
            ruc="80061234-5",
            defaults=dict(
                razon_social="Netlogic S.A.",
                nombre_comercial="Netlogic",
                tipo_contribuyente="JURIDICA",
                moneda_default=pyg,
                direccion="Av. Espana 2345, Asuncion, Paraguay",
                telefono="021-444-555",
                email="ventas@netlogic.com.py",
                timbrado_numero="12345678",
            ),
        )
        status = "creada" if created else "ya existe"
        self.stdout.write(f"  [OK] Empresa {status}: {empresa}")

        sucursal, _ = Sucursal.objects.get_or_create(
            empresa=empresa,
            codigo="001",
            defaults=dict(
                nombre="Casa Matriz Asuncion",
                direccion="Av. Espana 2345, Asuncion",
                telefono="021-444-555",
                es_casa_matriz=True,
            ),
        )
        self.stdout.write(f"  [OK] Sucursal: {sucursal.nombre}")

        sucursal2, _ = Sucursal.objects.get_or_create(
            empresa=empresa,
            codigo="002",
            defaults=dict(
                nombre="Sucursal Shopping del Sol",
                direccion="Shopping del Sol, Local 42, Asuncion",
                telefono="021-777-888",
                es_casa_matriz=False,
            ),
        )
        self.stdout.write(f"  [OK] Sucursal: {sucursal2.nombre}")

        deposito_principal, _ = Deposito.objects.get_or_create(
            sucursal=sucursal,
            codigo="DEP-01",
            defaults=dict(nombre="Almacen Principal", tipo="ALMACEN", permite_venta_directa=True),
        )
        deposito_transito, _ = Deposito.objects.get_or_create(  # noqa: F841
            sucursal=sucursal,
            codigo="DEP-02",
            defaults=dict(nombre="Transito", tipo="TRANSITO", permite_venta_directa=False),
        )
        deposito_shopping, _ = Deposito.objects.get_or_create(
            sucursal=sucursal2,
            codigo="DEP-03",
            defaults=dict(nombre="Almacen Shopping", tipo="ALMACEN", permite_venta_directa=True),
        )
        self.stdout.write("  [OK] Depositos: Almacen Principal, Transito, Shopping")

        PuntoVenta.objects.get_or_create(
            sucursal=sucursal,
            codigo="PV001",
            defaults=dict(
                nombre="Caja Principal",
                establecimiento="001",
                punto_expedicion="001",
                deposito_predeterminado=deposito_principal,
            ),
        )
        PuntoVenta.objects.get_or_create(
            sucursal=sucursal2,
            codigo="PV002",
            defaults=dict(
                nombre="Caja Shopping",
                establecimiento="002",
                punto_expedicion="001",
                deposito_predeterminado=deposito_shopping,
            ),
        )
        self.stdout.write("  [OK] Puntos de venta: PV001, PV002")

        self._pyg = pyg
        self._usd = usd
        self._sucursal = sucursal
        self._deposito = deposito_principal
        self._deposito2 = deposito_shopping

        self._seed_impuestos()
        self._seed_unidades()
        self._seed_marcas(empresa)
        self._seed_categorias(empresa)

        return empresa

    def _seed_impuestos(self):
        from apps.products.models import Impuesto
        self._iva10, _ = Impuesto.objects.get_or_create(
            nombre="IVA 10%", defaults=dict(tasa_porcentaje=Decimal("10.00"))
        )
        self._iva5, _ = Impuesto.objects.get_or_create(
            nombre="IVA 5%", defaults=dict(tasa_porcentaje=Decimal("5.00"))
        )
        self._exento, _ = Impuesto.objects.get_or_create(
            nombre="Exento", defaults=dict(tasa_porcentaje=Decimal("0.00"))
        )
        self.stdout.write("  [OK] Impuestos: IVA 10%, IVA 5%, Exento")

    def _seed_unidades(self):
        from apps.products.models import UnidadMedida
        unidades = [
            ("UN", "Unidad", False),
            ("KG", "Kilogramo", True),
            ("MT", "Metro lineal", True),
            ("LT", "Litro", True),
            ("CJ", "Caja", False),
            ("PAR", "Par", False),
            ("LIC", "Licencia", False),
        ]
        for codigo, nombre, decimales in unidades:
            UnidadMedida.objects.get_or_create(
                codigo=codigo, defaults=dict(nombre=nombre, permite_decimales=decimales)
            )
        self.stdout.write(f"  [OK] Unidades de medida: {len(unidades)}")
        self._um_un = UnidadMedida.objects.get(codigo="UN")
        self._um_mt = UnidadMedida.objects.get(codigo="MT")
        self._um_lic = UnidadMedida.objects.get(codigo="LIC")

    def _seed_marcas(self, empresa):
        from apps.products.models import Marca
        marcas_nombres = [
            "HP", "Dell", "Lenovo", "Cisco", "Samsung",
            "Logitech", "TP-Link", "Kingston", "LG", "APC",
            "Western Digital", "ASUS", "Epson", "Seagate", "Netlogic",
        ]
        self._marcas = {}
        for nombre in marcas_nombres:
            m, _ = Marca.objects.get_or_create(empresa=empresa, nombre=nombre)
            self._marcas[nombre] = m
        self.stdout.write(f"  [OK] Marcas: {len(marcas_nombres)}")

    def _seed_categorias(self, empresa):
        from apps.products.models import Categoria

        def cat(nombre, parent=None):
            c, _ = Categoria.objects.get_or_create(
                empresa=empresa, nombre=nombre, parent=parent
            )
            return c

        computadoras = cat("Computadoras")
        cat("Laptops", computadoras)
        cat("Desktops", computadoras)
        cat("All-in-One", computadoras)

        perifericos = cat("Perifericos")
        cat("Teclados y Mouse", perifericos)
        cat("Monitores", perifericos)
        cat("Impresoras y Scanners", perifericos)
        cat("Auriculares y Audio", perifericos)

        redes = cat("Redes")
        cat("Switches", redes)
        cat("Routers y Access Points", redes)
        cat("Cableado Estructurado", redes)

        cat("Almacenamiento")
        cat("Componentes")
        cat("Energia y UPS")
        cat("Servicios de TI")
        cat("Software y Licencias")

        self._cats = {c.nombre: c for c in Categoria.objects.filter(empresa=empresa)}
        self.stdout.write(f"  [OK] Categorias: {len(self._cats)}")

    # ------------------------------------------------------------------
    # 2. PROVEEDORES
    # ------------------------------------------------------------------
    def _seed_proveedores(self, empresa):
        from apps.suppliers.models import Proveedor
        proveedores_data = [
            ("80011111-1", "Intcomex Paraguay S.A.", "Intcomex",
             "Carlos Gomez", "021-333-001", "ventas@intcomex.com.py", "Av. Artigas 1500, Asuncion"),
            ("80022222-2", "Global PC Distribuidora", "Global PC",
             "Maria Lopez", "021-333-002", "ventas@globalpc.com.py", "Ruta 2 km 12, San Lorenzo"),
            ("80033333-3", "TechSource S.A.", "TechSource",
             "Pedro Ruiz", "021-333-003", "info@techsource.com.py", "Av. Eusebio Ayala 456, Asuncion"),
            ("80044444-4", "DigiTec S.R.L.", "DigiTec",
             "Ana Rodriguez", "021-333-004", "info@digitec.com.py", "Mcal. Lopez 789, Asuncion"),
            ("80055555-5", "Cisco Systems Paraguay", "Cisco PY",
             "Roberto Silva", "021-333-005", "py@cisco.com", "World Trade Center, Torre 1"),
        ]
        self._proveedores = {}
        for ruc, razon, nombre, contacto, tel, email, dir_ in proveedores_data:
            p, _ = Proveedor.objects.get_or_create(
                empresa=empresa, ruc=ruc,
                defaults=dict(
                    razon_social=razon, nombre_comercial=nombre,
                    contacto_nombre=contacto, telefono=tel,
                    email=email, direccion=dir_, moneda_default=self._pyg,
                ),
            )
            self._proveedores[nombre] = p
        self.stdout.write(f"  [OK] Proveedores: {len(proveedores_data)}")

    # ------------------------------------------------------------------
    # 3. CLIENTES
    # ------------------------------------------------------------------
    def _seed_clientes(self, empresa):
        from apps.customers.models import Cliente
        clientes_data = [
            ("80071111-1", "Banco Regional S.A.E.C.A.", "Banco Regional", "JURIDICA",
             "Juan Villalba", "021-417-5000", "sistemas@bancor.com.py", "Palma 401, Asuncion",
             Decimal("50000000"), 30, True),
            ("80072222-2", "Constructora Nande S.A.", "Nande Constructora", "JURIDICA",
             "Liz Acosta", "021-500-100", "compras@nande.com.py", "Av. Mcal. Lopez 1234",
             Decimal("25000000"), 15, False),
            ("80073333-3", "Ministerio de Hacienda", "Min. Hacienda", "JURIDICA",
             "Oficial Compras", "021-440-000", "tic@hacienda.gov.py", "Chile 128, Asuncion",
             Decimal("100000000"), 45, True),
            ("80074444-4", "Universidad Americana", "Univ. Americana", "JURIDICA",
             "Ing. Carlos Vera", "021-317-0900", "informatica@americana.edu.py", "Brazil 1080",
             Decimal("20000000"), 30, False),
            ("80075555-5", "Supermercados Stock S.A.", "Supermercados Stock", "JURIDICA",
             "Dep. TI", "021-600-200", "tecnologia@stock.com.py", "Av. San Martin 1500",
             Decimal("30000000"), 15, True),
            ("4567890-1", "Garcia & Asociados", "Garcia Consultores", "JURIDICA",
             "Andrea Garcia", "0981-111-222", "andrea@garcia.com.py", "Cerro Cora 987",
             Decimal("8000000"), 0, False),
            ("3456789-2", "Lopez Martinez Juan", "Juan Lopez", "FISICA",
             "Juan Lopez", "0981-333-444", "jlopez@gmail.com", "Las Residentas 456",
             Decimal("3000000"), 0, False),
            ("80076666-6", "Hospital Privado Santa Clara", "Sta. Clara", "JURIDICA",
             "Lic. Beatriz Nunez", "021-200-300", "sistemas@santaclara.com.py", "Av. Gral. Santos 500",
             Decimal("15000000"), 30, False),
            ("80077777-7", "Cooperativa Colonias Unidas", "Col. Unidas", "JURIDICA",
             "Dep. Sistemas", "074-242-000", "tic@coloniasunidas.coop", "Ruta 6 km 0, Alto Parana",
             Decimal("20000000"), 30, False),
            ("2345678-3", "Ramirez Torres Carlos", "Carlos Ramirez", "FISICA",
             "Carlos Ramirez", "0971-555-666", "cramirez@hotmail.com", "Luque",
             Decimal("0"), 0, False),
            ("80078888-8", "Telecom Paraguay S.A.", "Tigo", "JURIDICA",
             "Gerencia TI", "021-600-700", "proveedores@tigo.com.py", "Av. del Yacht 11",
             Decimal("80000000"), 30, True),
            ("80079999-9", "Petropar", "Petropar", "JURIDICA",
             "Jefatura Sistemas", "021-424-000", "sistemas@petropar.gov.py", "Oliva 395",
             Decimal("50000000"), 45, True),
            ("1234567-4", "Benitez Flores Maria", "Maria Benitez", "FISICA",
             "Maria Benitez", "0991-777-888", "mbenitez@gmail.com", "Fernando de la Mora",
             Decimal("1500000"), 0, False),
            ("80080000-5", "Agencia Pora Digital", "Pora Digital", "JURIDICA",
             "Lic. Diego Torres", "021-800-100", "dtorres@poradigital.com.py", "Av. Colon 1234",
             Decimal("5000000"), 15, False),
            ("80081111-6", "Instituto Tecnico Superior", "ITS Paraguay", "JURIDICA",
             "Rectorado", "021-900-200", "sistemas@its.edu.py", "Mcal. Estigarribia 789",
             Decimal("10000000"), 30, False),
        ]
        created_count = 0
        for ruc, razon, nombre, tipo, contacto, tel, email, dir_, limite, dias, vip in clientes_data:
            _, created = Cliente.objects.get_or_create(
                empresa=empresa, ruc=ruc,
                defaults=dict(
                    razon_social=razon, nombre_comercial=nombre,
                    tipo_contribuyente=tipo, contacto_nombre=contacto,
                    telefono=tel, email=email, direccion=dir_,
                    moneda_default=self._pyg, limite_credito=limite,
                    dias_credito=dias, es_vip=vip,
                ),
            )
            if created:
                created_count += 1
        self.stdout.write(f"  [OK] Clientes: {created_count} nuevos (total {len(clientes_data)})")

    # ------------------------------------------------------------------
    # 4. PRODUCTOS
    # ------------------------------------------------------------------
    def _seed_productos(self, empresa):
        from apps.products.models import Producto

        un = self._um_un
        mt = self._um_mt
        lic = self._um_lic
        iva10 = self._iva10
        iva5 = self._iva5
        pyg = self._pyg

        M = self._marcas
        C = self._cats
        P = self._proveedores

        productos_data = [
            # Laptops
            ("NB-HP-001", "Laptop HP ProBook 445 G9 AMD Ryzen 5 16GB 512GB SSD",
             M["HP"], C["Laptops"], P["Intcomex"], un, iva10,
             Decimal("3800000"), Decimal("4500000"), 3, 20),
            ("NB-HP-002", "Laptop HP 15s-eq Intel Core i5 8GB 256GB SSD",
             M["HP"], C["Laptops"], P["Intcomex"], un, iva10,
             Decimal("2900000"), Decimal("3500000"), 5, 25),
            ("NB-DL-001", "Laptop Dell Vostro 3520 Intel Core i7 16GB 512GB",
             M["Dell"], C["Laptops"], P["TechSource"], un, iva10,
             Decimal("4100000"), Decimal("4850000"), 3, 15),
            ("NB-LN-001", "Laptop Lenovo IdeaPad 3 AMD Ryzen 5 8GB 512GB",
             M["Lenovo"], C["Laptops"], P["Global PC"], un, iva10,
             Decimal("3200000"), Decimal("3900000"), 5, 20),
            ("NB-AS-001", "Laptop ASUS VivoBook 15 Intel i5 12GB 512GB SSD",
             M["ASUS"], C["Laptops"], P["DigiTec"], un, iva10,
             Decimal("3500000"), Decimal("4200000"), 3, 15),
            # Desktops
            ("PC-DL-001", "Desktop Dell Optiplex 3000 Intel Core i5 8GB 256GB",
             M["Dell"], C["Desktops"], P["TechSource"], un, iva10,
             Decimal("2600000"), Decimal("3200000"), 2, 10),
            ("PC-HP-001", "Desktop HP ProDesk 400 G9 Intel Core i5 8GB 512GB",
             M["HP"], C["Desktops"], P["Intcomex"], un, iva10,
             Decimal("2400000"), Decimal("2900000"), 2, 10),
            # Monitores
            ("MON-LG-024", "Monitor LG 24MP400-B 24 pulgadas Full HD IPS",
             M["LG"], C["Monitores"], P["DigiTec"], un, iva10,
             Decimal("980000"), Decimal("1250000"), 5, 30),
            ("MON-LG-027", "Monitor LG 27UK850-W 27 pulgadas 4K UHD IPS",
             M["LG"], C["Monitores"], P["DigiTec"], un, iva10,
             Decimal("1550000"), Decimal("1950000"), 3, 15),
            ("MON-SM-027", "Monitor Samsung 27 pulgadas Curvo FHD 144Hz",
             M["Samsung"], C["Monitores"], P["TechSource"], un, iva10,
             Decimal("1400000"), Decimal("1800000"), 3, 15),
            # Teclados y Mouse
            ("KBD-LG-001", "Kit Teclado + Mouse Logitech MK270 Inalambrico",
             M["Logitech"], C["Teclados y Mouse"], P["DigiTec"], un, iva10,
             Decimal("200000"), Decimal("280000"), 10, 50),
            ("MOU-LG-001", "Mouse Inalambrico Logitech M705 Marathon",
             M["Logitech"], C["Teclados y Mouse"], P["DigiTec"], un, iva10,
             Decimal("140000"), Decimal("195000"), 10, 40),
            # Switches y Redes
            ("SWT-CS-024", "Switch Cisco CBS110-24T 24 Puertos Gigabit No Gestionado",
             M["Cisco"], C["Switches"], P["Cisco PY"], un, iva10,
             Decimal("1900000"), Decimal("2400000"), 2, 10),
            ("SWT-CS-048", "Switch Cisco SG350-28P 28 Puertos PoE Gestionado",
             M["Cisco"], C["Switches"], P["Cisco PY"], un, iva10,
             Decimal("5800000"), Decimal("7200000"), 1, 5),
            ("RTR-TP-001", "Router TP-Link Archer AX23 WiFi 6 AX1800",
             M["TP-Link"], C["Routers y Access Points"], P["DigiTec"], un, iva10,
             Decimal("280000"), Decimal("380000"), 5, 25),
            ("AP-TP-001", "Access Point TP-Link EAP225 AC1350 Dual Band",
             M["TP-Link"], C["Routers y Access Points"], P["DigiTec"], un, iva10,
             Decimal("480000"), Decimal("650000"), 5, 20),
            # Cableado
            ("CAB-UTP-MT", "Cable UTP Cat6 Gris (precio por metro)",
             M["Netlogic"], C["Cableado Estructurado"], P["TechSource"], mt, iva10,
             Decimal("6000"), Decimal("8500"), 100, 2000),
            ("CAB-HDMI", "Cable HDMI 2.0 4K 1.8m",
             M["Netlogic"], C["Cableado Estructurado"], P["TechSource"], un, iva10,
             Decimal("45000"), Decimal("65000"), 15, 60),
            # Almacenamiento
            ("SSD-KG-480", "SSD Kingston A400 480GB SATA",
             M["Kingston"], C["Almacenamiento"], P["Global PC"], un, iva10,
             Decimal("320000"), Decimal("420000"), 10, 40),
            ("RAM-KG-8GB", "Memoria RAM Kingston 8GB DDR4 3200MHz",
             M["Kingston"], C["Almacenamiento"], P["Global PC"], un, iva10,
             Decimal("210000"), Decimal("290000"), 10, 40),
            ("USB-KG-064", "Pendrive Kingston DataTraveler 64GB USB 3.0",
             M["Kingston"], C["Almacenamiento"], P["Global PC"], un, iva10,
             Decimal("58000"), Decimal("85000"), 20, 80),
            ("HD-WD-1TB", "Disco Duro Externo WD Elements 1TB USB 3.0",
             M["Western Digital"], C["Almacenamiento"], P["DigiTec"], un, iva10,
             Decimal("380000"), Decimal("490000"), 5, 20),
            # Impresoras
            ("IMP-HP-001", "Impresora HP LaserJet Pro M404dn Monocromatica",
             M["HP"], C["Impresoras y Scanners"], P["Intcomex"], un, iva10,
             Decimal("1700000"), Decimal("2100000"), 2, 10),
            ("IMP-EP-001", "Impresora Epson EcoTank L3210 Multifuncional",
             M["Epson"], C["Impresoras y Scanners"], P["TechSource"], un, iva10,
             Decimal("1200000"), Decimal("1550000"), 3, 12),
            # UPS
            ("UPS-APC-600", "UPS APC Back-UPS 600VA 230V",
             M["APC"], C["Energia y UPS"], P["DigiTec"], un, iva10,
             Decimal("620000"), Decimal("780000"), 5, 20),
            ("UPS-APC-1200", "UPS APC Smart-UPS 1200VA SMT1200I",
             M["APC"], C["Energia y UPS"], P["DigiTec"], un, iva10,
             Decimal("2100000"), Decimal("2800000"), 2, 8),
            # Servicios
            ("SRV-MANT-PC", "Servicio Mantenimiento Preventivo PC",
             None, C["Servicios de TI"], None, un, iva10,
             Decimal("200000"), Decimal("250000"), 0, 0),
            ("SRV-MANT-RED", "Servicio Instalacion y Configuracion Red LAN",
             None, C["Servicios de TI"], None, un, iva10,
             Decimal("400000"), Decimal("500000"), 0, 0),
            ("SRV-SOPORTE", "Servicio Soporte Tecnico por Hora",
             None, C["Servicios de TI"], None, un, iva10,
             Decimal("80000"), Decimal("120000"), 0, 0),
            # Licencias
            ("LIC-WIN11-PRO", "Licencia Windows 11 Pro OEM",
             M["Netlogic"], C["Software y Licencias"], None, lic, iva5,
             Decimal("850000"), Decimal("1100000"), 5, 20),
            ("LIC-OFF365", "Licencia Microsoft 365 Business Basic 1 anio",
             M["Netlogic"], C["Software y Licencias"], None, lic, iva5,
             Decimal("650000"), Decimal("880000"), 5, 20),
            ("LIC-ANTIV", "Licencia Antivirus ESET NOD32 1 PC 1 anio",
             M["Netlogic"], C["Software y Licencias"], None, lic, iva5,
             Decimal("120000"), Decimal("175000"), 10, 40),
        ]

        created_count = 0
        self._productos = {}
        for row in productos_data:
            (codigo, nombre, marca, categoria, proveedor, um, impuesto,
             costo, precio, stock_min, stock_max) = row

            tipo = "SERVICIO" if categoria == C["Servicios de TI"] else "PRODUCTO"

            prod, created = Producto.objects.get_or_create(
                empresa=empresa,
                codigo=codigo,
                defaults=dict(
                    nombre=nombre,
                    tipo=tipo,
                    marca=marca,
                    categoria=categoria,
                    proveedor_principal=proveedor,
                    unidad_medida=um,
                    impuesto=impuesto,
                    moneda_costo=pyg,
                    costo=costo,
                    moneda_precio=pyg,
                    precio=precio,
                    stock_minimo=Decimal(str(stock_min)),
                    stock_maximo=Decimal(str(stock_max)),
                    metodo_costeo="PROMEDIO",
                    sku=codigo,
                ),
            )
            self._productos[codigo] = prod
            if created:
                created_count += 1

        self.stdout.write(f"  [OK] Productos: {created_count} nuevos (total {len(productos_data)})")

    # ------------------------------------------------------------------
    # 5. STOCK INICIAL
    # ------------------------------------------------------------------
    def _seed_stock(self, empresa):
        from apps.inventory.services import InventoryService
        from apps.inventory.models import StockBalance

        admin = User.objects.filter(is_superuser=True).first()
        if not admin:
            self.stdout.write("  [WARN] No hay superusuario: omitiendo stock inicial")
            return

        deposito = self._deposito
        deposito2 = self._deposito2

        stock_inicial = {
            "NB-HP-001":  (8,   2,  Decimal("3800000")),
            "NB-HP-002":  (10,  3,  Decimal("2900000")),
            "NB-DL-001":  (6,   1,  Decimal("4100000")),
            "NB-LN-001":  (8,   2,  Decimal("3200000")),
            "NB-AS-001":  (5,   1,  Decimal("3500000")),
            "PC-DL-001":  (4,   0,  Decimal("2600000")),
            "PC-HP-001":  (5,   1,  Decimal("2400000")),
            "MON-LG-024": (15,  4,  Decimal("980000")),
            "MON-LG-027": (6,   2,  Decimal("1550000")),
            "MON-SM-027": (8,   2,  Decimal("1400000")),
            "KBD-LG-001": (20,  5,  Decimal("200000")),
            "MOU-LG-001": (18,  4,  Decimal("140000")),
            "SWT-CS-024": (5,   1,  Decimal("1900000")),
            "SWT-CS-048": (2,   0,  Decimal("5800000")),
            "RTR-TP-001": (12,  3,  Decimal("280000")),
            "AP-TP-001":  (10,  2,  Decimal("480000")),
            "CAB-UTP-MT": (500, 200, Decimal("6000")),
            "CAB-HDMI":   (25,  8,  Decimal("45000")),
            "SSD-KG-480": (20,  5,  Decimal("320000")),
            "RAM-KG-8GB": (25,  6,  Decimal("210000")),
            "USB-KG-064": (35,  10, Decimal("58000")),
            "HD-WD-1TB":  (10,  3,  Decimal("380000")),
            "IMP-HP-001": (5,   1,  Decimal("1700000")),
            "IMP-EP-001": (7,   2,  Decimal("1200000")),
            "UPS-APC-600": (10, 3,  Decimal("620000")),
            "UPS-APC-1200": (3, 1,  Decimal("2100000")),
            "LIC-WIN11-PRO": (10, 0, Decimal("850000")),
            "LIC-OFF365": (10,  0,  Decimal("650000")),
            "LIC-ANTIV":  (20,  0,  Decimal("120000")),
        }

        movimientos = 0
        for codigo, (qty1, qty2, costo) in stock_inicial.items():
            producto = self._productos.get(codigo)
            if not producto or not producto.descuenta_stock:
                continue

            if qty1 > 0:
                tiene = StockBalance.objects.filter(
                    producto=producto, deposito=deposito, cantidad__gt=0
                ).exists()
                if not tiene:
                    InventoryService.registrar_entrada(
                        producto=producto, deposito=deposito,
                        cantidad=Decimal(str(qty1)), costo_unitario=costo,
                        moneda_costo_code="PYG", usuario=admin,
                        documento_tipo="APERTURA",
                        documento_referencia="SEED-NETLOGIC-2026",
                        observaciones="Stock inicial - carga de datos de prueba",
                    )
                    movimientos += 1

            if qty2 > 0:
                tiene2 = StockBalance.objects.filter(
                    producto=producto, deposito=deposito2, cantidad__gt=0
                ).exists()
                if not tiene2:
                    InventoryService.registrar_entrada(
                        producto=producto, deposito=deposito2,
                        cantidad=Decimal(str(qty2)), costo_unitario=costo,
                        moneda_costo_code="PYG", usuario=admin,
                        documento_tipo="APERTURA",
                        documento_referencia="SEED-NETLOGIC-2026",
                        observaciones="Stock inicial Shopping del Sol",
                    )
                    movimientos += 1

        self.stdout.write(f"  [OK] Movimientos de inventario creados: {movimientos}")

    # ------------------------------------------------------------------
    # 6. ASIGNAR SUPERUSUARIO
    # ------------------------------------------------------------------
    def _seed_cajas(self, empresa):
        from apps.treasury.models import Caja
        cajas_data = [
            (self._sucursal, "CJ-001", "Caja Principal"),
            (self._sucursal, "CJ-002", "Caja 2"),
        ]
        created = 0
        self._cajas = []
        for sucursal, codigo, nombre in cajas_data:
            pv = sucursal.puntos_venta.filter(active=True).first()
            c, is_new = Caja.objects.get_or_create(
                sucursal=sucursal, codigo=codigo,
                defaults=dict(empresa=empresa, nombre=nombre, punto_venta=pv),
            )
            self._cajas.append(c)
            if is_new:
                created += 1
        self.stdout.write(f"  [OK] Cajas: {created} nuevas (total {len(cajas_data)})")

    def _assign_superuser(self, empresa):
        updated = 0
        for user in User.objects.filter(is_superuser=True):
            if user.empresa_id != empresa.pk:
                user.empresa = empresa
                user.save(update_fields=["empresa"])
                updated += 1
        self.stdout.write(f"  [OK] Superusuarios asignados a Netlogic: {updated}")
        self.stdout.write(
            self.style.SUCCESS(
                f"\n  Empresa: {empresa}\n"
                f"  Admin:    http://127.0.0.1:8000/admin/\n"
                f"  Frontend: http://localhost:5173/"
            )
        )
