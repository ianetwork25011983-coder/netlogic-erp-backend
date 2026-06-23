"""
Test de integracion para todas las empresas y modulos del ERP.
Ejecutar con: python test_empresas.py
"""
import sys
import json
import urllib.request
import urllib.error

BASE = "http://127.0.0.1:8000"

EMPRESAS = [
    {"nombre": "Netlogic S.A. (TI)",       "email": "admin.netlogic@erptest.py",   "pw": "Admin1234!"},
    {"nombre": "Ferreteria Don Blas",       "email": "admin.ferreteria@erptest.py", "pw": "Admin1234!"},
    {"nombre": "Electro Centro S.A.",       "email": "admin.electro@erptest.py",    "pw": "Admin1234!"},
    {"nombre": "Supermercado La Plaza",     "email": "admin.plaza@erptest.py",      "pw": "Admin1234!"},
    {"nombre": "Agro Field S.R.L.",         "email": "admin.agro@erptest.py",       "pw": "Admin1234!"},
]

MODULOS = [
    ("Productos",    "/api/productos/"),
    ("Categorias",   "/api/categorias/"),
    ("Marcas",       "/api/marcas/"),
    ("Inventario",   "/api/inventory/saldos/"),
    ("Mov. Stock",   "/api/inventory/movimientos/"),
    ("Clientes",     "/api/clientes/"),
    ("Proveedores",  "/api/proveedores/"),
    ("Facturacion",  "/api/billing/documentos/"),
    ("Compras OC",   "/api/purchases/ordenes/"),
    ("Compras SC",   "/api/purchases/solicitudes/"),
    ("CRM Opps",     "/api/crm/oportunidades/"),
    ("CRM Prosp.",   "/api/crm/prospectos/"),
    ("Tesoreria",    "/api/treasury/cajas/"),
    ("T. Aperturas", "/api/treasury/aperturas/"),
    ("Pedidos",      "/api/orders/pedidos/"),
    ("Pricing",      "/api/pricing/listas-precio/"),
]

OK  = "[OK]"
ERR = "[ERR]"
WARN= "[WARN]"

total_ok  = 0
total_err = 0


def req(url, token=None, method="GET", data=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data else None
    r = urllib.request.Request(f"{BASE}{url}", data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(r, timeout=10) as resp:
            return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, {}
    except Exception as ex:
        return 0, {"error": str(ex)}


def login(email, pw):
    status, body = req("/api/auth/login/", method="POST", data={"email": email, "password": pw})
    if status == 200 and "access" in body:
        return body["access"], body.get("user", {})
    return None, {}


def count(body):
    if isinstance(body, dict):
        if "count" in body:
            return body["count"]
        if "results" in body:
            return len(body["results"])
        return len(body)
    if isinstance(body, list):
        return len(body)
    return "?"


print("=" * 65)
print("  TEST DE INTEGRACION - ERP NETLOGIC - TODAS LAS EMPRESAS")
print("=" * 65)

results_by_empresa = []

for empresa in EMPRESAS:
    print(f"\n{'-'*65}")
    print(f"  EMPRESA: {empresa['nombre']}")
    print(f"  Usuario: {empresa['email']}")
    print(f"{'-'*65}")

    token, user = login(empresa["email"], empresa["pw"])
    empresa_result = {"nombre": empresa["nombre"], "login": False, "modulos": {}}

    if not token:
        print(f"  {ERR} LOGIN FALLIDO para {empresa['email']}")
        total_err += 1
        results_by_empresa.append(empresa_result)
        continue

    empresa_nombre = user.get("empresa", {})
    if isinstance(empresa_nombre, dict):
        empresa_nombre = empresa_nombre.get("nombre_comercial") or empresa_nombre.get("razon_social") or "?"
    print(f"  {OK} Login exitoso -> Empresa: {empresa_nombre}")
    empresa_result["login"] = True
    total_ok += 1

    for mod_nombre, url in MODULOS:
        status, body = req(url, token=token)
        n = count(body)
        if status in (200, 201):
            print(f"  {OK} {mod_nombre:<15} -> {n} registros")
            empresa_result["modulos"][mod_nombre] = n
            total_ok += 1
        elif status == 404:
            print(f"  {WARN} {mod_nombre:<15} -> endpoint no encontrado (404)")
            empresa_result["modulos"][mod_nombre] = "404"
        elif status == 403:
            print(f"  {WARN} {mod_nombre:<15} -> sin permiso (403)")
            empresa_result["modulos"][mod_nombre] = "403"
        else:
            print(f"  {ERR} {mod_nombre:<15} -> status {status}")
            empresa_result["modulos"][mod_nombre] = f"ERR {status}"
            total_err += 1

    results_by_empresa.append(empresa_result)

# Verificar aislamiento de datos
print(f"\n{'-'*65}")
print("  VERIFICACION DE AISLAMIENTO MULTITENANT")
print(f"{'-'*65}")

tokens = {}
for empresa in EMPRESAS:
    t, _ = login(empresa["email"], empresa["pw"])
    if t:
        tokens[empresa["nombre"]] = t

if len(tokens) >= 2:
    empresas_nombres = list(tokens.keys())
    for i, nombre_a in enumerate(empresas_nombres[:3]):
        for nombre_b in empresas_nombres[i+1:i+2]:
            tok_a = tokens[nombre_a]
            tok_b = tokens[nombre_b]
            _, prods_a = req("/api/products/productos/", token=tok_a)
            _, prods_b = req("/api/products/productos/", token=tok_b)
            n_a = count(prods_a)
            n_b = count(prods_b)
            # Verify no product overlap via IDs
            ids_a = set()
            ids_b = set()
            if isinstance(prods_a, dict) and "results" in prods_a:
                ids_a = {p["id"] for p in prods_a["results"]}
            if isinstance(prods_b, dict) and "results" in prods_b:
                ids_b = {p["id"] for p in prods_b["results"]}
            overlap = ids_a & ids_b
            if overlap:
                print(f"  {ERR} Productos compartidos entre {nombre_a} y {nombre_b}: {len(overlap)} IDs")
                total_err += 1
            else:
                print(f"  {OK} Aislamiento OK: {nombre_a} ({n_a} prods) vs {nombre_b} ({n_b} prods) - sin solapamiento")
                total_ok += 1

# Resumen final
print(f"\n{'='*65}")
print(f"  RESUMEN FINAL")
print(f"{'='*65}")
for r in results_by_empresa:
    login_status = OK if r["login"] else ERR
    mods_ok = sum(1 for v in r["modulos"].values() if isinstance(v, int))
    mods_total = len(r["modulos"])
    print(f"  {login_status} {r['nombre']:<35} modulos: {mods_ok}/{mods_total}")

print(f"\n  Total checks OK : {total_ok}")
print(f"  Total checks ERR: {total_err}")
print(f"  Estado general  : {'PASSED' if total_err == 0 else 'CON ERRORES'}")
print("=" * 65)

