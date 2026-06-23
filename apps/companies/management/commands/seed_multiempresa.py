"""
Crea 4 empresas demo de distintos rubros con datos de muestra (multitenancy).

Cada empresa es totalmente independiente - ningun dato se comparte entre ellas.
El aislamiento es garantizado por ScopedToEmpresaMixin en el backend.

Empresas:
  1. Ferreteria Don Blas S.R.L.   -> admin.ferreteria@erptest.py / Admin1234!
  2. Electro Centro S.A.           -> admin.electro@erptest.py   / Admin1234!
  3. Supermercado La Plaza S.A.   -> admin.plaza@erptest.py     / Admin1234!
  4. Agro Field S.R.L.             -> admin.agro@erptest.py      / Admin1234!

Prerequisito: correr seed_netlogic primero (crea monedas, impuestos, unidades globales).
Uso:
    python manage.py seed_multiempresa
"""
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()

_PW = "Admin1234!"


class Command(BaseCommand):
    help = "Crea 4 empresas demo multitenancy (ferreteria, electrico, supermercado, agro)"

    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("=== Seed Multi-Empresa ==="))
        try:
            with transaction.atomic():
                self._load()
            self.stdout.write(self.style.SUCCESS("\nSeed completado correctamente"))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Error: {exc}"))
            import traceback
            self.stderr.write(traceback.format_exc())
            raise

    def _load(self):
        self._pyg = self._ensure_pyg()
        self._impuestos = self._ensure_impuestos()
        self._unidades = self._ensure_unidades()

        self._seed_netlogic_user()
        self._seed_ferreteria()
        self._seed_electrico()
        self._seed_supermercado()
        self._seed_agro()

        self.stdout.write("\nCredenciales de acceso:")
        self.stdout.write("  0) Netlogic TI : admin.netlogic@erptest.py  / Admin1234!")
        self.stdout.write("  1) Ferreteria  : admin.ferreteria@erptest.py / Admin1234!")
        self.stdout.write("  2) Electrico   : admin.electro@erptest.py   / Admin1234!")
        self.stdout.write("  3) Supermercado: admin.plaza@erptest.py     / Admin1234!")
        self.stdout.write("  4) Agro        : admin.agro@erptest.py      / Admin1234!")

    # ─────────────────────────────────────────────────────────────────────────
    # 0. NETLOGIC (empresa de TI creada por seed_netlogic)
    #    Solo crea el usuario admin dedicado; los datos ya existen.
    # ─────────────────────────────────────────────────────────────────────────
    def _seed_netlogic_user(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- 0. Netlogic S.A. (TI) ---"))
        from apps.companies.models import Empresa, Sucursal
        emp = Empresa.objects.filter(ruc="80061234-5").first()
        if not emp:
            self.stdout.write("  [WARN] Empresa Netlogic no encontrada. Correr seed_netlogic primero.")
            return
        suc = Sucursal.objects.filter(empresa=emp, es_casa_matriz=True).first()
        if suc:
            user, created = User.objects.get_or_create(
                email="admin.netlogic@erptest.py",
                defaults=dict(
                    first_name="Admin", last_name="Netlogic",
                    empresa=emp, is_active=True, is_staff=True,
                    must_change_password=False,
                ),
            )
            if created:
                user.set_password(_PW)
                user.save()
            else:
                if user.empresa_id != emp.pk:
                    user.empresa = emp
                    user.save(update_fields=["empresa"])
            user.sucursales.add(suc)
            self.stdout.write(f"  [OK] Netlogic: usuario admin.netlogic@erptest.py {'creado' if created else 'actualizado'}")
        else:
            self.stdout.write("  [WARN] Sin sucursal en Netlogic")

    # ─────────────────────────────────────────────────────────────────────────
    # OBJETOS GLOBALES (compartidos entre tenants, sin FK de empresa)
    # ─────────────────────────────────────────────────────────────────────────
    def _ensure_pyg(self):
        from apps.currencies.models import Currency
        pyg, _ = Currency.objects.get_or_create(
            code="PYG",
            defaults=dict(name="Guarani Paraguayo", symbol="Gs.", decimal_places=0, is_base=True),
        )
        return pyg

    def _ensure_impuestos(self):
        from apps.products.models import Impuesto
        iva10, _ = Impuesto.objects.get_or_create(
            nombre="IVA 10%", defaults=dict(tasa_porcentaje=Decimal("10.00"))
        )
        iva5, _ = Impuesto.objects.get_or_create(
            nombre="IVA 5%", defaults=dict(tasa_porcentaje=Decimal("5.00"))
        )
        exento, _ = Impuesto.objects.get_or_create(
            nombre="Exento", defaults=dict(tasa_porcentaje=Decimal("0.00"))
        )
        return {"IVA10": iva10, "IVA5": iva5, "Exento": exento}

    def _ensure_unidades(self):
        from apps.products.models import UnidadMedida
        data = [
            ("UN",  "Unidad",         False),
            ("KG",  "Kilogramo",      True),
            ("MT",  "Metro lineal",   True),
            ("LT",  "Litro",          True),
            ("CJ",  "Caja",           False),
            ("BOL", "Bolsa",          False),
            ("GL",  "Galon",          True),
            ("M2",  "Metro cuadrado", True),
            ("PAR", "Par",            False),
            ("SAC", "Saco",           False),
        ]
        units = {}
        for codigo, nombre, dec in data:
            u, _ = UnidadMedida.objects.get_or_create(
                codigo=codigo, defaults=dict(nombre=nombre, permite_decimales=dec)
            )
            units[codigo] = u
        return units

    # ─────────────────────────────────────────────────────────────────────────
    # HELPERS REUTILIZABLES
    # ─────────────────────────────────────────────────────────────────────────
    def _create_base(self, ruc, razon_social, nombre_comercial,
                     direccion, telefono, email, timbrado):
        from apps.companies.models import Empresa, Sucursal, Deposito, PuntoVenta
        emp, _ = Empresa.objects.get_or_create(
            ruc=ruc,
            defaults=dict(
                razon_social=razon_social, nombre_comercial=nombre_comercial,
                tipo_contribuyente="JURIDICA", moneda_default=self._pyg,
                direccion=direccion, telefono=telefono,
                email=email, timbrado_numero=timbrado,
            ),
        )
        suc, _ = Sucursal.objects.get_or_create(
            empresa=emp, codigo="001",
            defaults=dict(nombre="Casa Matriz", direccion=direccion,
                          telefono=telefono, es_casa_matriz=True),
        )
        dep, _ = Deposito.objects.get_or_create(
            sucursal=suc, codigo="DEP-01",
            defaults=dict(nombre="Almacen Principal", tipo="ALMACEN",
                          permite_venta_directa=True),
        )
        PuntoVenta.objects.get_or_create(
            sucursal=suc, codigo="PV001",
            defaults=dict(nombre="Caja Principal", establecimiento="001",
                          punto_expedicion="001", deposito_predeterminado=dep),
        )
        return emp, suc, dep

    def _create_caja(self, empresa, sucursal):
        from apps.treasury.models import Caja
        pv = sucursal.puntos_venta.filter(active=True).first()
        Caja.objects.get_or_create(
            sucursal=sucursal, codigo="CJ-001",
            defaults=dict(empresa=empresa, nombre="Caja Principal", punto_venta=pv),
        )

    def _create_user(self, email, first_name, last_name, empresa, sucursal):
        user, created = User.objects.get_or_create(
            email=email,
            defaults=dict(
                first_name=first_name, last_name=last_name,
                empresa=empresa, is_active=True, is_staff=True,
                must_change_password=False,
            ),
        )
        if created:
            user.set_password(_PW)
            user.save()
        else:
            if user.empresa_id != empresa.pk:
                user.empresa = empresa
                user.save(update_fields=["empresa"])
        user.sucursales.add(sucursal)
        return user

    def _mk(self, empresa, nombre):
        from apps.products.models import Marca
        m, _ = Marca.objects.get_or_create(empresa=empresa, nombre=nombre)
        return m

    def _cat(self, empresa, nombre, parent=None):
        from apps.products.models import Categoria
        c, _ = Categoria.objects.get_or_create(empresa=empresa, nombre=nombre, parent=parent)
        return c

    def _prod(self, empresa, codigo, nombre, tipo, precio, costo,
              unidad, marca, categoria, impuesto):
        from apps.products.models import Producto
        p, _ = Producto.objects.get_or_create(
            empresa=empresa, codigo=codigo,
            defaults=dict(
                nombre=nombre, tipo=tipo, precio=precio, costo=costo,
                moneda_precio=self._pyg, moneda_costo=self._pyg,
                unidad_medida=unidad, marca=marca, categoria=categoria,
                impuesto=impuesto, active=True,
            ),
        )
        return p

    def _stock(self, producto, deposito, cantidad, costo, usuario, ref):
        from apps.inventory.models import StockBalance
        from apps.inventory.services import InventoryService
        if not producto.descuenta_stock or cantidad <= 0:
            return
        existe = StockBalance.objects.filter(
            producto=producto, deposito=deposito, cantidad__gt=0
        ).exists()
        if not existe:
            InventoryService.registrar_entrada(
                producto=producto, deposito=deposito,
                cantidad=cantidad, costo_unitario=costo,
                moneda_costo_code="PYG", usuario=usuario,
                documento_tipo="APERTURA", documento_referencia=ref,
                observaciones="Stock inicial demo multiempresa",
            )

    def _proveedores(self, empresa, data):
        from apps.suppliers.models import Proveedor
        for ruc, razon, nombre, contacto, tel, email in data:
            Proveedor.objects.get_or_create(
                empresa=empresa, ruc=ruc,
                defaults=dict(
                    razon_social=razon, nombre_comercial=nombre,
                    contacto_nombre=contacto, telefono=tel,
                    email=email, moneda_default=self._pyg,
                ),
            )

    def _clientes(self, empresa, data):
        from apps.customers.models import Cliente
        for ruc, razon, nombre, contacto, tel, email in data:
            Cliente.objects.get_or_create(
                empresa=empresa, ruc=ruc,
                defaults=dict(
                    razon_social=razon, nombre_comercial=nombre,
                    contacto_nombre=contacto, telefono=tel,
                    email=email, moneda_default=self._pyg,
                ),
            )

    # ═════════════════════════════════════════════════════════════════════════
    # 1. FERRETERIA DON BLAS S.R.L.
    # ═════════════════════════════════════════════════════════════════════════
    def _seed_ferreteria(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- 1. Ferreteria Don Blas ---"))
        emp, suc, dep = self._create_base(
            ruc="80111111-1",
            razon_social="Ferreteria Don Blas S.R.L.",
            nombre_comercial="Don Blas Ferreteria",
            direccion="Mcal. Estigarribia 1234, Luque, Paraguay",
            telefono="0228-432-100",
            email="ventas@donblas.com.py",
            timbrado="11111111",
        )
        admin = self._create_user("admin.ferreteria@erptest.py", "Carlos", "Benitez", emp, suc)
        self._create_caja(emp, suc)

        self._proveedores(emp, [
            ("90111001-1", "Materiales Don Anibal S.A.", "Don Anibal", "Juan Vera", "0228-555-001", "ventas@donanibal.com.py"),
            ("90111002-2", "Distribuidora Ferretera Nacional", "Ferro Nacional", "Pedro Meza", "021-555-002", "info@ferronacional.com.py"),
            ("90111003-3", "Pinturas ALBA S.A.", "ALBA Paraguay", "Ana Flores", "021-555-003", "ventas@albapintura.com.py"),
            ("90111004-4", "Cementos Itapua S.A.", "Itapua", "Luis Torres", "071-555-004", "ventas@itapua.com.py"),
            ("90111005-5", "Electrica del Sur S.A.", "Electrica Sur", "Mario Gimenez", "021-555-005", "info@electricasur.com.py"),
        ])
        self._clientes(emp, [
            ("90211001-1", "Constructora Rojas S.A.", "Constructora Rojas", "Miguel Rojas", "0981-700-001", "mrojas@constrojas.com.py"),
            ("90211002-2", "Municipalidad de Luque", "Muni Luque", "Ing. Sandra Pena", "0228-100-200", "licitaciones@luque.gov.py"),
            ("90211003-3", "Inmobiliaria Primavera S.A.", "Primavera", "Carlos Gimenez", "0981-700-003", "cgimenez@primavera.com.py"),
            ("90211004-4", "Alba Construcciones S.R.L.", "Alba Const.", "Roberto Alba", "0991-700-004", "alba@albaconstrucciones.com.py"),
            ("90211005-5", "Hogares Modernos S.A.", "Hogares Modernos", "Diana Lopez", "0981-700-005", "dlopez@hogaresmodernos.com.py"),
            ("90211006-6", "Empresa Constructora ABC S.A.", "Const. ABC", "Mario Benitez", "021-700-006", "info@constabc.com.py"),
            ("90211007-7", "Pinturas y Mas S.R.L.", "Pinturas y Mas", "Felix Rivarola", "0991-700-007", "felix@pinturasmas.com.py"),
            ("90211008-8", "Ferreteria El Amigo", "El Amigo", "Rosa Amarilla", "0228-700-008", "rosa@elamigo.com.py"),
            ("90211009-9", "Cooperativa San Juan Ltda.", "Coop. San Juan", "Antonio Gaona", "0271-700-009", "agaona@coopsanjuan.com.py"),
            ("90211010-0", "Empresa de Servicios Generales", "Serv. Generales", "Blanca Ruiz", "021-700-010", "bruiz@servgenerales.com.py"),
        ])

        # Categorias
        herr   = self._cat(emp, "Herramientas Manuales")
        hpow   = self._cat(emp, "Herramientas Electricas")
        mat    = self._cat(emp, "Materiales de Construccion")
        pint   = self._cat(emp, "Pinturas y Accesorios")
        plom   = self._cat(emp, "Plomeria")
        elec   = self._cat(emp, "Electricidad")
        seg    = self._cat(emp, "Seguridad y EPP")
        fij    = self._cat(emp, "Fijaciones y Tornillos")

        # Marcas
        stanley    = self._mk(emp, "Stanley")
        tramontina = self._mk(emp, "Tramontina")
        bosch      = self._mk(emp, "Bosch")
        alba       = self._mk(emp, "ALBA")
        celta      = self._mk(emp, "Celta")
        itapua_m   = self._mk(emp, "Itapua")
        generico   = self._mk(emp, "Generico")
        makita     = self._mk(emp, "Makita")

        iva10 = self._impuestos["IVA10"]
        iva5  = self._impuestos["IVA5"]
        un = self._unidades["UN"]
        kg = self._unidades["KG"]
        lt = self._unidades["LT"]
        mt = self._unidades["MT"]
        m2 = self._unidades["M2"]

        # (codigo, nombre, tipo, precio, costo, unidad, marca, cat, impuesto, stock_qty)
        prods = [
            ("FE-001", "Martillo carpintero 20oz Stanley",    "PRODUCTO", Decimal("75000"), Decimal("55000"), un, stanley,    herr, iva10, 30),
            ("FE-002", "Llave inglesa 10\" ajustable",        "PRODUCTO", Decimal("62000"), Decimal("45000"), un, stanley,    herr, iva10, 25),
            ("FE-003", "Set destornilladores 6 piezas",       "PRODUCTO", Decimal("48000"), Decimal("35000"), un, stanley,    herr, iva10, 40),
            ("FE-004", "Alicate universal 8\"",               "PRODUCTO", Decimal("38000"), Decimal("28000"), un, tramontina, herr, iva10, 35),
            ("FE-005", "Nivel burbuja aluminio 60cm",         "PRODUCTO", Decimal("55000"), Decimal("40000"), un, bosch,      herr, iva10, 20),
            ("FE-006", "Cinta metrica 5m acero",              "PRODUCTO", Decimal("22000"), Decimal("15000"), un, stanley,    herr, iva10, 60),
            ("FE-007", "Serrucho 22\" carpintero",            "PRODUCTO", Decimal("45000"), Decimal("32000"), un, tramontina, herr, iva10, 18),
            ("FE-008", "Pala redonda mango madera",           "PRODUCTO", Decimal("68000"), Decimal("50000"), un, generico,   herr, iva10, 20),
            ("FE-009", "Amoladora angular 4.5\" 850W",        "PRODUCTO", Decimal("320000"), Decimal("240000"), un, bosch,   hpow, iva10, 8),
            ("FE-010", "Taladro percutor 500W 13mm",          "PRODUCTO", Decimal("285000"), Decimal("210000"), un, makita,  hpow, iva10, 10),
            ("FE-011", "Cemento Itapua bolsa 50kg",           "PRODUCTO", Decimal("85000"), Decimal("68000"), kg, itapua_m,  mat,  iva5, 200),
            ("FE-012", "Cal hidratada bolsa 20kg",            "PRODUCTO", Decimal("32000"), Decimal("24000"), kg, generico,  mat,  iva5, 80),
            ("FE-013", "Arena gruesa bolsa 40kg",             "PRODUCTO", Decimal("28000"), Decimal("20000"), kg, generico,  mat,  iva5, 100),
            ("FE-014", "Ceramica piso 60x60 caja x6",         "PRODUCTO", Decimal("95000"), Decimal("72000"), m2, generico,  mat,  iva10, 60),
            ("FE-015", "Cano PVC 4\" x 3m sanitario",         "PRODUCTO", Decimal("72000"), Decimal("54000"), un, celta,     plom, iva10, 40),
            ("FE-016", "Cano PVC 2\" x 3m",                  "PRODUCTO", Decimal("42000"), Decimal("32000"), un, celta,     plom, iva10, 50),
            ("FE-017", "Llave de paso 1/2\" bronce",          "PRODUCTO", Decimal("35000"), Decimal("26000"), un, celta,     plom, iva10, 30),
            ("FE-018", "Codo PVC 90g 2\"",                    "PRODUCTO", Decimal("8500"),  Decimal("6000"),  un, celta,     plom, iva10, 100),
            ("FE-019", "Pintura latex blanco 4lt",            "PRODUCTO", Decimal("125000"), Decimal("95000"), lt, alba,     pint, iva10, 50),
            ("FE-020", "Pintura esmalte negro brillante 1lt", "PRODUCTO", Decimal("65000"), Decimal("48000"), lt, alba,     pint, iva10, 30),
            ("FE-021", "Pintura antihumedad 4lt",             "PRODUCTO", Decimal("145000"), Decimal("110000"), lt, alba,   pint, iva10, 25),
            ("FE-022", "Aguarras mineral 1lt",                "PRODUCTO", Decimal("22000"), Decimal("16000"), lt, generico, pint, iva10, 40),
            ("FE-023", "Rodillo lana 23cm con mango",         "PRODUCTO", Decimal("18000"), Decimal("13000"), un, generico, pint, iva10, 60),
            ("FE-024", "Cable unipolar 2.5mm x100m",          "PRODUCTO", Decimal("185000"), Decimal("145000"), mt, generico, elec, iva10, 15),
            ("FE-025", "Tomacorriente doble empotrado",        "PRODUCTO", Decimal("12000"), Decimal("8500"),  un, generico, elec, iva10, 80),
            ("FE-026", "Interruptor simple",                  "PRODUCTO", Decimal("9500"),  Decimal("6800"),  un, generico, elec, iva10, 100),
            ("FE-027", "Lampara LED 9W E27 luz fria",         "PRODUCTO", Decimal("22000"), Decimal("16000"), un, generico, elec, iva10, 80),
            ("FE-028", "Casco de seguridad blanco",           "PRODUCTO", Decimal("45000"), Decimal("32000"), un, generico, seg,  iva10, 30),
            ("FE-029", "Guantes cuero vacuno par",            "PRODUCTO", Decimal("28000"), Decimal("20000"), un, generico, seg,  iva10, 50),
            ("FE-030", "Tornillos 6x60mm caja x100",          "PRODUCTO", Decimal("18000"), Decimal("12000"), un, generico, fij,  iva10, 100),
        ]
        cnt = 0
        for c, n, t, pr, co, u, mk, ca, im, sq in prods:
            p = self._prod(emp, c, n, t, pr, co, u, mk, ca, im)
            self._stock(p, dep, Decimal(str(sq)), co, admin, "SEED-FERRETERIA")
            cnt += 1
        self.stdout.write(f"  [OK] Ferreteria: {cnt} productos, 10 clientes, 5 proveedores")

    # ═════════════════════════════════════════════════════════════════════════
    # 2. ELECTRO CENTRO S.A.
    # ═════════════════════════════════════════════════════════════════════════
    def _seed_electrico(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- 2. Electro Centro S.A. ---"))
        emp, suc, dep = self._create_base(
            ruc="80222222-2",
            razon_social="Electro Centro S.A.",
            nombre_comercial="Electro Centro",
            direccion="Av. Mariscal Lopez 4567, Asuncion, Paraguay",
            telefono="021-612-700",
            email="ventas@electrocentro.com.py",
            timbrado="22222222",
        )
        admin = self._create_user("admin.electro@erptest.py", "Sandra", "Vega", emp, suc)
        self._create_caja(emp, suc)

        self._proveedores(emp, [
            ("90222001-1", "ABB Paraguay S.A.", "ABB", "Rodrigo Diaz", "021-666-001", "py@abb.com"),
            ("90222002-2", "Schneider Electric Paraguay", "Schneider", "Valeria Ruiz", "021-666-002", "valeria@schneider.com.py"),
            ("90222003-3", "Siemens Paraguay S.A.", "Siemens", "Kurt Muller", "021-666-003", "kmuller@siemens.com.py"),
            ("90222004-4", "Distribuidora Electrica Asuncion", "Dist. Electrica", "Carmen Lopez", "021-666-004", "clopez@distelectrica.com.py"),
            ("90222005-5", "Osram Paraguay S.A.", "Osram", "Daniel Fretes", "021-666-005", "dfretes@osram.com.py"),
        ])
        self._clientes(emp, [
            ("90322001-1", "Constructora Andino S.A.", "Andino", "Julio Andino", "0981-800-001", "jandino@andino.com.py"),
            ("90322002-2", "Industrias Guarani S.A.", "Ind. Guarani", "Pablo Garay", "021-800-002", "pgaray@indguarani.com.py"),
            ("90322003-3", "Hospital Privado Recoleta", "H. Recoleta", "Dra. Maria Vega", "021-800-003", "tecnica@recoleta.com.py"),
            ("90322004-4", "Hotel Excelsior S.A.", "Hotel Excelsior", "Ing. Pedro Torres", "021-800-004", "mantenimiento@excelsior.com.py"),
            ("90322005-5", "Centro Comercial Paseo La Galeria", "La Galeria", "Arq. Rosa Ayala", "021-800-005", "rayala@lagaleria.com.py"),
            ("90322006-6", "Universidad Nacional del Este", "UNE", "Ing. Cesar Lopez", "061-800-006", "infraestructura@une.edu.py"),
            ("90322007-7", "Frigorifico Chortitzer S.A.", "Chortitzer", "Ing. Hans Unger", "0521-800-007", "hunger@chortitzer.com.py"),
            ("90322008-8", "Supermercados Vea S.A.", "Vea", "Lic. Silvia Meza", "021-800-008", "smeza@vea.com.py"),
            ("90322009-9", "Empresa Distribuidora ANDE", "ANDE Dist.", "Ing. Victor Alvarez", "021-800-009", "valvarez@ande.gov.py"),
            ("90322010-0", "Planta Industrial Madame Lynch", "Planta Lynch", "Ing. Diana Flores", "021-800-010", "dflores@plantamlynch.com.py"),
        ])

        # Categorias
        cables   = self._cat(emp, "Cables y Conductores")
        tableros = self._cat(emp, "Tableros y Protecciones")
        ilum     = self._cat(emp, "Iluminacion")
        motores  = self._cat(emp, "Motores y Variadores")
        acces    = self._cat(emp, "Accesorios Electricos")
        auto     = self._cat(emp, "Automatizacion")
        energias = self._cat(emp, "Energia Solar")

        # Marcas
        abb       = self._mk(emp, "ABB")
        schneider = self._mk(emp, "Schneider Electric")
        siemens   = self._mk(emp, "Siemens")
        osram     = self._mk(emp, "Osram")
        philips   = self._mk(emp, "Philips")
        generico  = self._mk(emp, "Generico")
        camsco    = self._mk(emp, "Camsco")

        iva10 = self._impuestos["IVA10"]
        un = self._unidades["UN"]
        mt = self._unidades["MT"]
        kg = self._unidades["KG"]

        prods = [
            ("EL-001", "Cable unipolar 1.5mm NYA x100m",      "PRODUCTO", Decimal("92000"),  Decimal("70000"),  mt,       generico,  cables,   iva10, 20),
            ("EL-002", "Cable unipolar 2.5mm NYA x100m",      "PRODUCTO", Decimal("145000"), Decimal("112000"), mt,       generico,  cables,   iva10, 20),
            ("EL-003", "Cable unipolar 4mm NYA x100m",        "PRODUCTO", Decimal("210000"), Decimal("162000"), mt,       generico,  cables,   iva10, 15),
            ("EL-004", "Cable mellizo 2x1.5mm x50m",          "PRODUCTO", Decimal("78000"),  Decimal("59000"),  mt,       generico,  cables,   iva10, 25),
            ("EL-005", "Cable apantallado 4x1.5mm x100m",     "PRODUCTO", Decimal("320000"), Decimal("248000"), mt,       schneider, cables,   iva10, 8),
            ("EL-006", "Breaker 1x10A curva C",               "PRODUCTO", Decimal("28000"),  Decimal("20000"),  un,       abb,       tableros, iva10, 50),
            ("EL-007", "Breaker 1x16A curva C",               "PRODUCTO", Decimal("30000"),  Decimal("22000"),  un,       abb,       tableros, iva10, 50),
            ("EL-008", "Breaker 2x32A curva C",               "PRODUCTO", Decimal("68000"),  Decimal("52000"),  un,       abb,       tableros, iva10, 30),
            ("EL-009", "Breaker trifasico 3x63A",             "PRODUCTO", Decimal("145000"), Decimal("112000"), un,       schneider, tableros, iva10, 15),
            ("EL-010", "Tablero metalico 12 termicos",        "PRODUCTO", Decimal("185000"), Decimal("142000"), un,       camsco,    tableros, iva10, 12),
            ("EL-011", "Riel DIN 35mm x1m",                  "PRODUCTO", Decimal("12000"),  Decimal("8500"),   mt,       generico,  tableros, iva10, 40),
            ("EL-012", "Lampara LED 9W E27 luz fria",         "PRODUCTO", Decimal("22000"),  Decimal("16000"),  un,       osram,     ilum,     iva10, 100),
            ("EL-013", "Lampara LED tubo 18W T8 x60cm",       "PRODUCTO", Decimal("32000"),  Decimal("24000"),  un,       philips,   ilum,     iva10, 80),
            ("EL-014", "Luminaria industrial LED 100W",       "PRODUCTO", Decimal("285000"), Decimal("220000"), un,       philips,   ilum,     iva10, 20),
            ("EL-015", "Foco dicroico LED 7W GU10",           "PRODUCTO", Decimal("18000"),  Decimal("13000"),  un,       osram,     ilum,     iva10, 80),
            ("EL-016", "Reflector LED 50W exterior",          "PRODUCTO", Decimal("95000"),  Decimal("72000"),  un,       philips,   ilum,     iva10, 30),
            ("EL-017", "Contactor 25A 220V 2NO+2NC",          "PRODUCTO", Decimal("78000"),  Decimal("60000"),  un,       schneider, auto,     iva10, 20),
            ("EL-018", "Rele termico 6-10A",                  "PRODUCTO", Decimal("52000"),  Decimal("40000"),  un,       abb,       auto,     iva10, 15),
            ("EL-019", "Variador frecuencia 1HP 220V",        "PRODUCTO", Decimal("320000"), Decimal("248000"), un,       siemens,   motores,  iva10, 6),
            ("EL-020", "Motor electrico 1HP 1750rpm",         "PRODUCTO", Decimal("450000"), Decimal("348000"), un,       siemens,   motores,  iva10, 5),
            ("EL-021", "Tomacorriente doble seguridad",        "PRODUCTO", Decimal("15000"),  Decimal("11000"),  un,       generico,  acces,    iva10, 100),
            ("EL-022", "Interruptor bipolar 10A",             "PRODUCTO", Decimal("12000"),  Decimal("8800"),   un,       generico,  acces,    iva10, 100),
            ("EL-023", "Caja octogonal PVC empotrar",         "PRODUCTO", Decimal("6500"),   Decimal("4700"),   un,       generico,  acces,    iva10, 150),
            ("EL-024", "Cano conduit 1\" x 3m",              "PRODUCTO", Decimal("28000"),  Decimal("21000"),  un,       generico,  acces,    iva10, 50),
            ("EL-025", "Panel solar 400W monocristalino",     "PRODUCTO", Decimal("850000"), Decimal("660000"), un,       generico,  energias, iva10, 10),
            ("EL-026", "Inversor solar 3000W 24V",            "PRODUCTO", Decimal("1200000"), Decimal("950000"), un,      generico,  energias, iva10, 5),
            ("EL-027", "Bateria solar 100Ah 12V AGM",         "PRODUCTO", Decimal("480000"), Decimal("370000"), un,       generico,  energias, iva10, 10),
            ("EL-028", "Terminal punta a compresion 16mm",    "PRODUCTO", Decimal("4200"),   Decimal("3000"),   un,       generico,  acces,    iva10, 200),
            ("EL-029", "Cinta aisladora 3M 19mm x20m",       "PRODUCTO", Decimal("8500"),   Decimal("6200"),   un,       generico,  acces,    iva10, 80),
            ("EL-030", "Multimetro digital profesional",      "PRODUCTO", Decimal("125000"), Decimal("96000"),  un,       generico,  acces,    iva10, 15),
        ]
        cnt = 0
        for c, n, t, pr, co, u, mk, ca, im, sq in prods:
            p = self._prod(emp, c, n, t, pr, co, u, mk, ca, im)
            self._stock(p, dep, Decimal(str(sq)), co, admin, "SEED-ELECTRICO")
            cnt += 1
        self.stdout.write(f"  [OK] Electro Centro: {cnt} productos, 10 clientes, 5 proveedores")

    # ═════════════════════════════════════════════════════════════════════════
    # 3. SUPERMERCADO LA PLAZA S.A.
    # ═════════════════════════════════════════════════════════════════════════
    def _seed_supermercado(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- 3. Supermercado La Plaza ---"))
        emp, suc, dep = self._create_base(
            ruc="80333333-3",
            razon_social="Supermercado La Plaza S.A.",
            nombre_comercial="La Plaza Supermercado",
            direccion="Shopping Multiplaza, Asuncion, Paraguay",
            telefono="021-777-888",
            email="ventas@laplazasuper.com.py",
            timbrado="33333333",
        )
        admin = self._create_user("admin.plaza@erptest.py", "Maria", "Gonzalez", emp, suc)
        self._create_caja(emp, suc)

        self._proveedores(emp, [
            ("90333001-1", "Distribuidora Dias S.A.", "Dist. Dias", "Oscar Dias", "021-999-001", "odias@distdias.com.py"),
            ("90333002-2", "Copacol Paraguay S.A.", "Copacol", "Sandra Monges", "021-999-002", "smonges@copacol.com.py"),
            ("90333003-3", "Distribuidora de Lacteos Central", "Lacteos Central", "Elena Rios", "021-999-003", "erios@lacteoscentral.com.py"),
            ("90333004-4", "Bebidas Golosa S.A.", "Golosa", "Felipe Roa", "021-999-004", "froa@golosa.com.py"),
            ("90333005-5", "Limpieza y Hogar Dist.", "Limpieza Hogar", "Graciela Vega", "021-999-005", "gvega@limpiezahogar.com.py"),
            ("90333006-6", "Frigorifico Chortitzer S.A.", "Chortitzer", "Hans Koop", "0521-999-006", "hkoop@chortitzer.com.py"),
        ])
        self._clientes(emp, [
            ("90433001-1", "Restaurant El Portal S.R.L.", "El Portal", "Juan Escobar", "0981-900-001", "jescobar@elportal.com.py"),
            ("90433002-2", "Empresa de Catering Gourmet", "Catering Gourmet", "Rosa Mendez", "0991-900-002", "rmendez@cateringgourmet.com.py"),
            ("90433003-3", "Hotel Sabe Mi S.A.", "Hotel Sabe Mi", "Pedro Salave", "021-900-003", "psalave@hotelsabemi.com.py"),
            ("90433004-4", "Comedor Universitario UNA", "Comedor UNA", "Lic. Felix Aquino", "021-900-004", "faquino@una.py"),
            ("90433005-5", "Empresa de Limpieza Total S.R.L.", "Limpieza Total", "Claudia Amarilla", "0981-900-005", "camarilla@limpiezatotal.com.py"),
            ("90433006-6", "Panaderia y Confiteria Ykua S.A.", "Ykua", "Luis Ykua", "021-900-006", "luisykua@panaderiaykua.com.py"),
            ("90433007-7", "Colegio Privado San Francisco", "Colegio SF", "Hermana Clara", "021-900-007", "admin@colegsanfran.edu.py"),
            ("90433008-8", "Clinica Medica Santa Clara", "Sta. Clara", "Dra. Julia Bernal", "021-900-008", "farmacia@santaclara.com.py"),
            ("90433009-9", "Empresa de Seguridad Guardia Plus", "Guardia Plus", "Walter Cabrera", "0991-900-009", "wcabrera@guardiaplus.com.py"),
            ("90433010-0", "Municipalidad de Asuncion", "Muni Asuncion", "Lic. Tania Pino", "021-900-010", "tpino@asuncion.gov.py"),
        ])

        # Categorias
        alim   = self._cat(emp, "Alimentos basicos")
        bebid  = self._cat(emp, "Bebidas")
        lacte  = self._cat(emp, "Lacteos y Frios")
        carnes = self._cat(emp, "Carnes y Embutidos")
        higien = self._cat(emp, "Higiene Personal")
        limp   = self._cat(emp, "Limpieza del Hogar")
        confec = self._cat(emp, "Confiteria y Snacks")
        frutas = self._cat(emp, "Frutas y Verduras")

        # Marcas
        dorado  = self._mk(emp, "Dorado")
        manon   = self._mk(emp, "Manon")
        pepsi   = self._mk(emp, "Pepsi")
        coca    = self._mk(emp, "Coca-Cola")
        pradera = self._mk(emp, "La Pradera")
        chor    = self._mk(emp, "Chortitzer")
        dove    = self._mk(emp, "Dove")
        ariel   = self._mk(emp, "Ariel")
        generico = self._mk(emp, "Sin Marca")

        iva10 = self._impuestos["IVA10"]
        iva5  = self._impuestos["IVA5"]
        exento = self._impuestos["Exento"]
        un  = self._unidades["UN"]
        kg  = self._unidades["KG"]
        lt  = self._unidades["LT"]

        prods = [
            # Alimentos
            ("SP-001", "Arroz Dorado extra 1kg",             "PRODUCTO", Decimal("6500"),  Decimal("4800"),  un, dorado,  alim,   exento, 500),
            ("SP-002", "Fideos largos 500g",                 "PRODUCTO", Decimal("4200"),  Decimal("3100"),  un, dorado,  alim,   exento, 400),
            ("SP-003", "Aceite de maiz 900ml",               "PRODUCTO", Decimal("16500"), Decimal("12500"), un, manon,   alim,   iva5, 300),
            ("SP-004", "Azucar Manon 1kg",                   "PRODUCTO", Decimal("5800"),  Decimal("4300"),  un, manon,   alim,   exento, 400),
            ("SP-005", "Sal refinada 1kg",                   "PRODUCTO", Decimal("2500"),  Decimal("1800"),  un, generico,alim,   exento, 300),
            ("SP-006", "Harina 0000 1kg",                    "PRODUCTO", Decimal("5200"),  Decimal("3800"),  un, manon,   alim,   exento, 250),
            ("SP-007", "Yerba mate 1kg",                     "PRODUCTO", Decimal("18000"), Decimal("13500"), un, generico,alim,   exento, 200),
            ("SP-008", "Porotos negros 500g",                "PRODUCTO", Decimal("7500"),  Decimal("5600"),  un, dorado,  alim,   exento, 150),
            # Bebidas
            ("SP-009", "Gaseosa Pepsi 2.25lt",               "PRODUCTO", Decimal("12000"), Decimal("9000"),  un, pepsi,   bebid,  iva10, 300),
            ("SP-010", "Agua mineral sin gas 1.5lt",         "PRODUCTO", Decimal("5500"),  Decimal("4000"),  un, generico,bebid,  iva10, 400),
            ("SP-011", "Gaseosa Coca-Cola 2lt",              "PRODUCTO", Decimal("11500"), Decimal("8600"),  un, coca,    bebid,  iva10, 300),
            ("SP-012", "Jugo tropical 1lt",                  "PRODUCTO", Decimal("8500"),  Decimal("6300"),  un, generico,bebid,  iva10, 200),
            ("SP-013", "Cerveza Brahma lata 350ml",          "PRODUCTO", Decimal("7500"),  Decimal("5600"),  un, generico,bebid,  iva10, 200),
            # Lacteos
            ("SP-014", "Leche La Pradera entera 1lt",        "PRODUCTO", Decimal("7800"),  Decimal("5900"),  un, pradera, lacte,  iva5, 300),
            ("SP-015", "Yogur natural 500g",                 "PRODUCTO", Decimal("9500"),  Decimal("7100"),  un, pradera, lacte,  iva5, 100),
            ("SP-016", "Queso Paraguay fresco 250g",         "PRODUCTO", Decimal("18000"), Decimal("13500"), un, chor,    lacte,  iva5, 100),
            ("SP-017", "Mantequilla sin sal 200g",           "PRODUCTO", Decimal("16000"), Decimal("12000"), un, chor,    lacte,  iva5, 80),
            # Carnes
            ("SP-018", "Carne molida premium 1kg",           "PRODUCTO", Decimal("35000"), Decimal("28000"), kg, chor,    carnes, iva5, 100),
            ("SP-019", "Pollo entero 1.5kg aprox.",          "PRODUCTO", Decimal("28000"), Decimal("22000"), kg, chor,    carnes, iva5, 80),
            ("SP-020", "Salchicha Chortitzer 500g",          "PRODUCTO", Decimal("22000"), Decimal("17000"), un, chor,    carnes, iva5, 120),
            # Higiene
            ("SP-021", "Jabon de tocador Dove 90g",          "PRODUCTO", Decimal("8500"),  Decimal("6300"),  un, dove,    higien, iva10, 200),
            ("SP-022", "Champu Pantene 400ml",               "PRODUCTO", Decimal("32000"), Decimal("24000"), un, generico,higien, iva10, 100),
            ("SP-023", "Papel higienico x4 doble hoja",      "PRODUCTO", Decimal("18000"), Decimal("13500"), un, generico,higien, iva10, 200),
            ("SP-024", "Pasta dental Colgate 90g",           "PRODUCTO", Decimal("14500"), Decimal("10800"), un, generico,higien, iva10, 150),
            # Limpieza
            ("SP-025", "Detergente Ariel 1kg",               "PRODUCTO", Decimal("28000"), Decimal("21000"), un, ariel,   limp,   iva10, 150),
            ("SP-026", "Lavandina 1lt",                      "PRODUCTO", Decimal("5500"),  Decimal("4100"),  lt, generico,limp,   iva10, 200),
            ("SP-027", "Esponja lavar platos x2",            "PRODUCTO", Decimal("4500"),  Decimal("3300"),  un, generico,limp,   iva10, 200),
            ("SP-028", "Limpiador multiusos 500ml",          "PRODUCTO", Decimal("12000"), Decimal("9000"),  un, generico,limp,   iva10, 120),
            # Confiteria
            ("SP-029", "Galletas surtidas 400g",             "PRODUCTO", Decimal("12000"), Decimal("9000"),  un, generico,confec, iva10, 150),
            ("SP-030", "Chocolatinas x10 surtidas",          "PRODUCTO", Decimal("15000"), Decimal("11000"), un, generico,confec, iva10, 100),
        ]
        cnt = 0
        for c, n, t, pr, co, u, mk, ca, im, sq in prods:
            p = self._prod(emp, c, n, t, pr, co, u, mk, ca, im)
            self._stock(p, dep, Decimal(str(sq)), co, admin, "SEED-SUPERMERCADO")
            cnt += 1
        self.stdout.write(f"  [OK] Supermercado La Plaza: {cnt} productos, 10 clientes, 6 proveedores")

    # ═════════════════════════════════════════════════════════════════════════
    # 4. AGRO FIELD S.R.L.
    # ═════════════════════════════════════════════════════════════════════════
    def _seed_agro(self):
        self.stdout.write(self.style.MIGRATE_HEADING("\n--- 4. Agro Field S.R.L. ---"))
        emp, suc, dep = self._create_base(
            ruc="80444444-4",
            razon_social="Agro Field S.R.L.",
            nombre_comercial="Agro Field",
            direccion="Ruta 7 km 45, Coronel Oviedo, Paraguay",
            telefono="0521-200-300",
            email="ventas@agrofield.com.py",
            timbrado="44444444",
        )
        admin = self._create_user("admin.agro@erptest.py", "Roberto", "Campos", emp, suc)
        self._create_caja(emp, suc)

        self._proveedores(emp, [
            ("90444001-1", "Cargill Agricola S.A.", "Cargill", "Daniel Vargas", "0521-888-001", "dvargas@cargill.com.py"),
            ("90444002-2", "Monsanto Paraguay S.A.", "Monsanto", "Paula Koenig", "021-888-002", "pkoenig@monsanto.com.py"),
            ("90444003-3", "Syngenta Paraguay S.A.", "Syngenta", "Marcos Salinas", "021-888-003", "msalinas@syngenta.com.py"),
            ("90444004-4", "Distribuidora Agroquimica Nacional", "Dist. Agro", "Elena Maidana", "0521-888-004", "emaidana@distagro.com.py"),
            ("90444005-5", "Maquinarias Agricolas del Sur", "Maq. del Sur", "Antonio Fretes", "0521-888-005", "afretes@maqsur.com.py"),
        ])
        self._clientes(emp, [
            ("90544001-1", "Estancia San Rafael S.R.L.", "Estancia San Rafael", "Jorge Rafael", "0981-700-101", "jrafael@estanciasr.com.py"),
            ("90544002-2", "Cooperativa Agricola Colonias Unidas", "Colon. Unidas", "Hans Braun", "0767-700-102", "hbraun@coloniasunidas.com.py"),
            ("90544003-3", "Soja Paraguay S.A.", "Soja Paraguay", "Ricardo Solis", "0521-700-103", "rsolis@sojapy.com.py"),
            ("90544004-4", "Frigorifico Concepcion S.A.", "Frigo Concepcion", "Miguel Trujillo", "031-700-104", "mtrujillo@frigoconcep.com.py"),
            ("90544005-5", "Arroces del Parana S.A.", "Arroces Parana", "Cecilia Ibarra", "0521-700-105", "cibarra@arrocesparana.com.py"),
            ("90544006-6", "Agro-Servicio Capiata", "AgroServ Capiata", "Julio Capiata", "021-700-106", "jcapiata@agroservcapiata.com.py"),
            ("90544007-7", "Empresa Ganadera Los Algarrobos", "Los Algarrobos", "Pedro Algarrobo", "0971-700-107", "palgarrobo@losalgarrobos.com.py"),
            ("90544008-8", "Municipalidad de Caaguazu", "Muni Caaguazu", "Ing. Ana Barrios", "0522-700-108", "abarrios@caaguazu.gov.py"),
            ("90544009-9", "Productores Unidos del Norte", "Prod. Norte", "Victor Morel", "031-700-109", "vmorel@prodnorte.com.py"),
            ("90544010-0", "Granja Familiar Paraiso Verde", "Paraiso Verde", "Lidia Jacquet", "0981-700-110", "ljacquet@paraisoverde.com.py"),
        ])

        # Categorias
        semillas   = self._cat(emp, "Semillas")
        fertil     = self._cat(emp, "Fertilizantes")
        agroquim   = self._cat(emp, "Agroquimicos")
        herr_agro  = self._cat(emp, "Herramientas Agricolas")
        riego      = self._cat(emp, "Sistemas de Riego")
        maquinaria = self._cat(emp, "Maquinaria Agricola")
        sacos_a    = self._cat(emp, "Sacos y Embalajes")

        # Marcas
        monsanto = self._mk(emp, "Monsanto")
        syngenta = self._mk(emp, "Syngenta")
        nidera   = self._mk(emp, "Nidera")
        yara     = self._mk(emp, "Yara")
        bayer    = self._mk(emp, "Bayer")
        generico = self._mk(emp, "Generico")
        naan     = self._mk(emp, "Naan-Dan Jain")

        iva10  = self._impuestos["IVA10"]
        iva5   = self._impuestos["IVA5"]
        exento = self._impuestos["Exento"]
        un  = self._unidades["UN"]
        kg  = self._unidades["KG"]
        lt  = self._unidades["LT"]
        sac = self._unidades["SAC"]
        mt  = self._unidades["MT"]

        prods = [
            # Semillas
            ("AG-001", "Semilla soja NK-7201 bolsa 40kg",         "PRODUCTO", Decimal("385000"), Decimal("298000"), sac, monsanto, semillas,   iva10, 80),
            ("AG-002", "Semilla soja DM-6.8i bolsa 40kg",         "PRODUCTO", Decimal("365000"), Decimal("282000"), sac, nidera,   semillas,   iva10, 60),
            ("AG-003", "Semilla maiz NK-Silver bolsa 60000s",     "PRODUCTO", Decimal("428000"), Decimal("330000"), un,  monsanto, semillas,   iva10, 40),
            ("AG-004", "Semilla sorgo granifero 5kg",             "PRODUCTO", Decimal("95000"),  Decimal("73000"),  sac, syngenta, semillas,   iva10, 30),
            ("AG-005", "Semilla papa Red Pontiac 25kg",           "PRODUCTO", Decimal("185000"), Decimal("142000"), sac, generico, semillas,   iva10, 20),
            ("AG-006", "Semilla girasol DK-3820 bolsa 5kg",      "PRODUCTO", Decimal("155000"), Decimal("119000"), sac, nidera,   semillas,   iva10, 25),
            # Fertilizantes
            ("AG-007", "Urea granulada 46% N saco 50kg",         "PRODUCTO", Decimal("185000"), Decimal("143000"), sac, yara,     fertil,     iva5, 200),
            ("AG-008", "MAP fosfato monoamonico saco 50kg",      "PRODUCTO", Decimal("225000"), Decimal("174000"), sac, yara,     fertil,     iva5, 150),
            ("AG-009", "Superfosfato triple saco 50kg",          "PRODUCTO", Decimal("198000"), Decimal("153000"), sac, yara,     fertil,     iva5, 120),
            ("AG-010", "Nitrato de amonio saco 50kg",            "PRODUCTO", Decimal("175000"), Decimal("135000"), sac, generico, fertil,     iva5, 100),
            ("AG-011", "Fertilizante foliar liquido 1lt",        "PRODUCTO", Decimal("85000"),  Decimal("65000"),  lt,  yara,     fertil,     iva5, 60),
            # Agroquimicos
            ("AG-012", "Glifosato 48% SL 1lt (Roundup)",        "PRODUCTO", Decimal("48000"),  Decimal("37000"),  lt,  monsanto, agroquim,   iva10, 200),
            ("AG-013", "Fungicida Tebuconazole 250ml",           "PRODUCTO", Decimal("95000"),  Decimal("73000"),  lt,  bayer,    agroquim,   iva10, 80),
            ("AG-014", "Insecticida Clorpirifos 480ml",         "PRODUCTO", Decimal("62000"),  Decimal("48000"),  lt,  syngenta, agroquim,   iva10, 60),
            ("AG-015", "Herbicida Atrazina 500ml",              "PRODUCTO", Decimal("42000"),  Decimal("32000"),  lt,  syngenta, agroquim,   iva10, 80),
            ("AG-016", "Insecticida Clorpirifos 1lt",           "PRODUCTO", Decimal("78000"),  Decimal("60000"),  lt,  syngenta, agroquim,   iva10, 50),
            # Herramientas agricolas
            ("AG-017", "Fumigadora de mochila 20lt manual",     "PRODUCTO", Decimal("185000"), Decimal("142000"), un,  generico, herr_agro,  iva10, 25),
            ("AG-018", "Fumigadora de mochila 16lt electrica",  "PRODUCTO", Decimal("295000"), Decimal("228000"), un,  generico, herr_agro,  iva10, 15),
            ("AG-019", "Azada doble mango largo",               "PRODUCTO", Decimal("68000"),  Decimal("52000"),  un,  generico, herr_agro,  iva10, 30),
            ("AG-020", "Pala ancha agricola mango largo",       "PRODUCTO", Decimal("72000"),  Decimal("55000"),  un,  generico, herr_agro,  iva10, 25),
            ("AG-021", "Carretilla metalica 80lt",              "PRODUCTO", Decimal("185000"), Decimal("142000"), un,  generico, herr_agro,  iva10, 15),
            # Riego
            ("AG-022", "Manguera de riego 1/2\" x 50m",        "PRODUCTO", Decimal("95000"),  Decimal("73000"),  un,  generico, riego,      iva10, 30),
            ("AG-023", "Aspersor impacto bronce 1/2\" 360g",   "PRODUCTO", Decimal("28000"),  Decimal("21000"),  un,  naan,     riego,      iva10, 40),
            ("AG-024", "Gotero boton autocompensante 2 L/h",   "PRODUCTO", Decimal("2500"),   Decimal("1800"),   un,  naan,     riego,      iva10, 200),
            ("AG-025", "Cinta de goteo 16mm x200m",            "PRODUCTO", Decimal("285000"), Decimal("220000"), mt,  naan,     riego,      iva10, 10),
            # Maquinaria
            ("AG-026", "Bomba de riego 1HP centrifuga",        "PRODUCTO", Decimal("485000"), Decimal("375000"), un,  generico, maquinaria, iva10, 5),
            ("AG-027", "Sembradora manual de maiz 1 surco",    "PRODUCTO", Decimal("285000"), Decimal("220000"), un,  generico, maquinaria, iva10, 5),
            # Sacos
            ("AG-028", "Saco de polipropileno blanco 60kg x100", "PRODUCTO", Decimal("85000"),  Decimal("65000"),  un,  generico, sacos_a,    iva10, 50),
            ("AG-029", "Film stretch 500m para silos",          "PRODUCTO", Decimal("225000"), Decimal("174000"), un,  generico, sacos_a,    iva10, 20),
            ("AG-030", "Bolsa kraft multiwall 25kg x100",       "PRODUCTO", Decimal("95000"),  Decimal("73000"),  un,  generico, sacos_a,    iva10, 30),
        ]
        cnt = 0
        for c, n, t, pr, co, u, mk, ca, im, sq in prods:
            p = self._prod(emp, c, n, t, pr, co, u, mk, ca, im)
            self._stock(p, dep, Decimal(str(sq)), co, admin, "SEED-AGRO")
            cnt += 1
        self.stdout.write(f"  [OK] Agro Field: {cnt} productos, 10 clientes, 5 proveedores")



