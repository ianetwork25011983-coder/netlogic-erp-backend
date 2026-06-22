# ERP Stock — Fase 0 a Fase 7 (los 19 módulos completos + motor de reglas)

Base del ERP de stock, facturación e inteligencia de inventario.

**Fase 0** entrega el esqueleto del proyecto y los tres módulos transversales:

- **Módulo 1 — Seguridad y Accesos**: login por email, MFA/TOTP con
  códigos de respaldo, auditoría completa, historial de accesos, roles
  con alcance por empresa/sucursal, bloqueo por intentos fallidos.
- **Módulo 2 — Empresas y Sucursales**: multiempresa, sucursales,
  depósitos ilimitados, centros de distribución, puntos de venta con
  numeración fiscal (timbrado).
- **Núcleo de Monedas**: PYG como moneda base, USD/BRL/ARS como monedas
  operativas, tasas de cambio históricas cargadas manualmente, servicio
  de conversión usado transversalmente por el resto del ERP.

**Fase 1** agrega:

- **Módulo 3 — Maestro de Productos**: productos, servicios, combos,
  kits, productos compuestos (con BOM/lista de componentes), control por
  lote/serie/vencimiento, marcas, categorías jerárquicas, unidades de
  medida, impuestos. App `apps.suppliers` con un modelo mínimo de
  Proveedor (se expande en Fase 2 - Compras).
- **Módulo 4 — Control Avanzado de Inventario**: Kardex completo e
  inmutable, saldos en tiempo real, costeo FIFO/LIFO/Promedio Ponderado
  por producto, entradas, salidas, transferencias entre depósitos,
  ajustes manuales, conteo físico/cíclico con generación automática de
  ajuste por diferencia, ubicaciones (rack/pasillo/estantería/nivel),
  inventario valorizado.

**Fase 2** agrega:

- **Módulo 9 — Compras**: solicitudes de compra, cotizaciones de
  proveedores (con comparación de costo/plazo/condiciones), órdenes de
  compra, recepción de mercadería (parcial o total, conectada
  automáticamente a `InventoryService`), facturas de proveedor. App
  `apps.customers` con un modelo mínimo de Cliente (se expande en Fase 3
  - CRM).
- **Módulo 10 — Facturación**: un único modelo `DocumentoVenta` cubre
  Factura, Nota de Crédito, Nota de Débito, Presupuesto y Remisión, con
  numeración fiscal correlativa por punto de venta, múltiples monedas
  (con snapshot de tipo de cambio al emitir), múltiples tasas de
  impuesto por línea (con desglose para facturación electrónica),
  conversión Presupuesto → Factura, y anulación con reverso automático
  de stock cuando corresponde.

**Fase 3** agrega:

- **Módulo 6 — CRM**: prospectos con conversión a Cliente (migrando sus
  contactos automáticamente), contactos (de Cliente o de Prospecto),
  pipeline de ventas configurable por empresa (etapas ordenadas, con
  marca de "ganada"/"perdida"), oportunidades con valor estimado y
  probabilidad, historial de interacciones (llamadas/emails/reuniones/
  notas) con seguimiento programable (`fecha_proxima_accion`).
- **Módulo 7 — Portal de Clientes**: autenticación **propia** y aislada
  de la de empleados (`PortalUser` + `PortalJWTAuthentication`, con un
  claim de JWT distinto — un token de portal nunca autentica en
  endpoints internos, ni viceversa). El cliente puede iniciar sesión,
  ver sus pedidos y su seguimiento, consultar stock disponible,
  descargar/listar sus facturas y presupuestos, ver su estado de cuenta,
  y solicitar nuevos pedidos.
- **Módulo 8 — Gestión de Pedidos Web**: flujo completo Carrito →
  Validación automática → Reserva de stock → Aprobación → Picking →
  Facturación → Despacho → Entrega, con historial de cada transición de
  estado. Incluye listas de precios múltiples (`apps.pricing`),
  promociones automáticas por producto/categoría, y cupones de
  descuento (validados por vigencia, usos y monto mínimo). La reserva de
  stock es una "reserva blanda" (`StockReserva`, agregada al Módulo 4)
  que no toca el Kardex hasta que el pedido se factura.

**Fase 4** agrega:

- **Módulo 11 — Caja y Tesorería**: apertura/cierre de caja con arqueo
  (compara lo contado contra lo esperado en efectivo y deja la
  diferencia documentada), ingresos/egresos por concepto y medio de
  pago, cobro de facturas (actualiza `DocumentoVenta.saldo_pendiente`) y
  pago a proveedores (actualiza `FacturaProveedor.saldo_pendiente` y su
  estado), bancos/cuentas bancarias con su propio libro de movimientos.
- **Módulo 12 — Logística**: transportistas, vehículos y rutas; Picking
  (con detalle de qué se tomó de qué ubicación) y Packing (bultos/peso/
  volumen) ligados 1 a 1 con el `PedidoWeb` del Módulo 8; Despacho
  (consolidando uno o más documentos de venta en una misma salida) y
  registro de Entrega. Despachar/entregar dispara automáticamente las
  transiciones correspondientes en `OrderService` (Módulo 8), para que
  el estado del pedido y el estado logístico nunca queden desincronizados.

**Fase 5** agrega:

- **Módulo 13 — Dashboard Ejecutivo**: indicadores de ventas, compras,
  rentabilidad/margen, rotación de inventario (aproximada) e inventario
  valorizado; series temporales por día/semana/mes para gráficos;
  comparativo automático contra el período anterior; top productos y
  top clientes. Todo en vivo, sin tabla de caché (push en tiempo real
  por WebSocket queda como mejora futura, igual que el seguimiento de
  pedidos).
- **Módulo 14 — Reportes**: exportación a Excel (Kardex, inventario
  valorizado, ventas, compras, clientes, proveedores, rentabilidad por
  producto) vía `openpyxl`, y generación de PDF de Factura/Presupuesto/
  NC/ND vía `WeasyPrint` con desglose de IVA — esto resuelve el
  pendiente de PDF que quedó abierto desde la Fase 2.

**Fase 6** agrega (y completa las 19 módulos del prompt original):

- **Módulo 5 — IA de Inventario**: predicción de demanda (promedio móvil
  + tendencia lineal sobre el historial de ventas, sin requerir ML
  entrenado), reposición inteligente (punto de reposición, stock mínimo/
  máximo sugeridos usando desviación estándar de la demanda — fórmula
  clásica de gestión de inventario), sugerencias automáticas de compra y
  de transferencia entre depósitos, y detección de anomalías (sobre
  stock, rotación lenta, obsolescencia, productos críticos).
- **Módulo 17 — Business Intelligence**: clasificación ABC (Pareto) de
  productos y clientes, detección de clientes en declive (comparando
  contra el período anterior), rotación de inventario por categoría.
- **Módulo 19 — IA Copiloto del ERP**: responde en lenguaje natural las
  5 preguntas de ejemplo del enunciado original (qué comprar esta
  semana, qué productos rotan lento, margen del mes pasado, qué
  clientes bajaron sus compras, generar una orden de compra sugerida) y
  varias más, con detección de intención por patrones — **no es un LLM**,
  es un router de reglas sobre los servicios ya construidos en las fases
  anteriores. Queda documentado el camino de upgrade a un LLM real.

**Fase 7** agrega (cierra el prompt original completo):

- **Módulo 15 — Documentación de la API**: Swagger UI en `/api/docs/`,
  Redoc en `/api/redoc/`, y el esquema OpenAPI crudo en `/api/schema/`,
  vía `drf-spectacular`. Las ~200 rutas del ERP quedan documentadas
  automáticamente a partir del código (sin mantener documentación a mano).
- **Módulo 16 — Motor de Reglas configurable**: `ReglaAutomatizacion`
  permite crear desde la API (sin tocar código) reglas tipo
  SI-condición-ENTONCES-acción sobre Productos o Pedidos Web. Cubre
  exactamente los 3 ejemplos del prompt original: stock bajo el mínimo →
  generar solicitud de compra (con cantidad sugerida automática), producto
  sin movimiento > N días → generar alerta, cliente VIP hace un pedido →
  asignar prioridad (vía señal automática al crear el pedido). Cada
  evaluación, cumpla o no la condición, queda en `EjecucionRegla` para auditoría.

No se usa Docker, según lo solicitado. Todo se instala directo sobre el
sistema (o un virtualenv) y se conecta a PostgreSQL/Redis ya instalados.

---

## 1. Requisitos previos (instalar en el servidor/PC, sin Docker)

- Python 3.13 (el proyecto se desarrolló y probó también contra 3.12,
  compatible con Django 5.x)
- PostgreSQL 15+ corriendo localmente o accesible por red (la Fase 1 usa
  `UniqueConstraint(nulls_distinct=False)`, que requiere Postgres 15+)
- Redis 7+ corriendo localmente o accesible por red (cache, Celery, Channels)
- Librerías de sistema para WeasyPrint (generación de PDF, Fase 5):
  `sudo apt install libpango-1.0-0 libpangocairo-1.0-0 libcairo2 libgdk-pixbuf2.0-0`

### Crear la base de datos en PostgreSQL

```bash
sudo -u postgres psql
CREATE DATABASE erp_stock;
CREATE USER erp_stock_user WITH PASSWORD 'tu-password-segura';
GRANT ALL PRIVILEGES ON DATABASE erp_stock TO erp_stock_user;
\q
```

## 2. Instalación del proyecto

```bash
python3 -m venv .venv
source .venv/bin/activate          # En Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Copiar `.env.example` a `.env` y completar con tus credenciales reales:

```bash
cp .env.example .env
```

Generar una `DJANGO_SECRET_KEY` real (no usar la del ejemplo):

```bash
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 3. Migraciones y superusuario

```bash
python manage.py migrate
python manage.py createsuperuser
```

> Nota: el modelo de usuario es custom (login por email, sin `username`).
> `createsuperuser` te va a pedir email, nombre y apellido.

## 4. Carga inicial de datos (monedas + catálogos base)

Antes de operar, cargar el catálogo de monedas desde el admin
(`/admin/currencies/currency/`) o por shell:

```bash
python manage.py shell
```
```python
from apps.currencies.models import Currency
Currency.objects.create(code="PYG", name="Guaraní", symbol="₲", decimal_places=0, is_base=True)
Currency.objects.create(code="USD", name="Dólar", symbol="$", decimal_places=2)
Currency.objects.create(code="BRL", name="Real", symbol="R$", decimal_places=2)
Currency.objects.create(code="ARS", name="Peso Argentino", symbol="$", decimal_places=2)

from apps.products.models import UnidadMedida
UnidadMedida.objects.create(codigo="UN", nombre="Unidad")
UnidadMedida.objects.create(codigo="KG", nombre="Kilogramo")
```

Luego cargar las tasas de cambio del día desde
`/admin/currencies/exchangerate/` (o vía API, ver abajo).

## 5. Levantar el servidor de desarrollo

```bash
python manage.py runserver
```

Para Channels/Celery en producción (no Docker, procesos del sistema vía
systemd, igual que tus otros proyectos Django):

```bash
# Worker de Celery
celery -A config worker -l info

# Beat (tareas periódicas, ej. recordatorio de cargar tasa de cambio diaria)
celery -A config beat -l info

# Servidor ASGI (para Channels en producción)
daphne -b 0.0.0.0 -p 8001 config.asgi:application
```

---

## 6. Tests

La suite usa `pytest` + `pytest-django`, corre contra **SQLite en
memoria** (no necesita Postgres/Redis reales levantados) y vive como
`tests.py` dentro de cada app — convención estándar de Django, fácil de
ubicar.

```bash
pip install -r requirements.txt   # ya incluye pytest, pytest-django, pytest-cov
python -m pytest                  # toda la suite (~165 tests)
python -m pytest apps/inventory/  # solo una app
python -m pytest -v               # detalle por test
python -m pytest --cov=apps --cov-report=term-missing   # con cobertura
```

La cobertura está concentrada en la **capa de servicios** (`services.py`
de cada app — donde vive la lógica de negocio real: costeo FIFO/LIFO/
Promedio, facturación con multi-impuesto, motor de reglas, etc.), no en
el detalle de cada endpoint REST uno por uno — esos son en su mayoría
wrappers finos sobre los servicios ya cubiertos, y los más críticos
(login/MFA, aislamiento del portal, copiloto) sí tienen tests de API
explícitos. Cobertura global actual: **~84%**, con los módulos de
servicios casi todos por encima del 90%.

Lo que ya cubre la suite (organizado por lo que realmente importa, no
por archivo):
- Conversión de monedas multi-divisa y tasas históricas.
- Login, MFA (TOTP + códigos de respaldo), bloqueo por intentos fallidos.
- Costeo FIFO, LIFO y Promedio Ponderado; transferencias; ajustes;
  conteo físico; reservas de stock.
- Recepción de compras → entrada de inventario.
- Facturación con multi-impuesto, Nota de Crédito, anulación con
  reverso de stock, descuento global.
- Conversión de prospecto a cliente, pipeline de ventas.
- Cupones, listas de precio, promociones.
- El flujo completo de Pedidos Web (carrito → validación → reserva →
  aprobación → picking → facturación → despacho → entrega).
- **El aislamiento de autenticación del Portal de Clientes en ambas
  direcciones** (el test de seguridad más importante de todo el proyecto).
- Apertura/cierre de caja con arqueo, cobro de facturas, pago a
  proveedores, movimientos bancarios.
- Picking → Packing → Despacho → Entrega, con la orquestación hacia
  `OrderService`.
- Indicadores del dashboard (ventas, rentabilidad, inventario) y
  generación real de Excel/PDF.
- Predicción de demanda, reposición inteligente, detección de
  anomalías, sugerencia de transferencias.
- Clasificación ABC y detección de clientes en declive.
- Las 10 intenciones del Copiloto (las 5 del prompt original + 5 variantes).
- **Los 3 ejemplos exactos del motor de reglas** del prompt original.

Durante la escritura de esta suite se encontraron y corrigieron **dos
bugs reales** que no habían aparecido en las pruebas manuales de fases
anteriores:
1. La clasificación ABC (`apps/bi/services.py`) tenía la lógica de
   umbral invertida: un único producto dominante (>95% de las ventas)
   terminaba clasificado como "C" en vez de "A", porque el umbral se
   evaluaba con el acumulado DESPUÉS de sumar el ítem en vez de ANTES.
   Ya corregido y con test de regresión.
2. (Menor, sin impacto funcional) Confirmación de que
   `proyeccion_demanda_mensual` nunca devuelve `"insuficiente_historial"`
   con los parámetros por defecto, porque `historial_ventas_mensual`
   siempre incluye al menos el mes actual — el código está bien, era una
   suposición incorrecta sobre cuándo se activa ese caso límite.

---

## Endpoints disponibles

### Autenticación (`/api/auth/`)
| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/auth/login/` | Login. Si el usuario tiene MFA, devuelve `mfa_token` en vez de los tokens finales. |
| POST | `/api/auth/mfa/verify/` | Segundo factor: `{mfa_token, otp_code}` → devuelve `access`/`refresh`. |
| POST | `/api/auth/mfa/enroll/` | Inicia alta de MFA (devuelve secreto + URI para QR). Requiere estar autenticado. |
| POST | `/api/auth/mfa/enroll/confirm/` | Confirma el primer código y activa MFA (devuelve `backup_codes`, una sola vez). |
| POST | `/api/auth/mfa/disable/` | Desactiva MFA. |
| GET | `/api/auth/me/` | Perfil del usuario autenticado. |
| GET | `/api/auth/login-history/` | Historial de accesos propios. |
| CRUD | `/api/auth/users/`, `/api/auth/roles/`, `/api/auth/role-assignments/` | Gestión de usuarios y roles. |

### Empresas (`/api/`)
- CRUD en `/api/empresas/`, `/api/sucursales/`, `/api/depositos/`, `/api/puntos-venta/`

### Monedas (`/api/currencies/`)
- CRUD en `/api/currencies/currencies/`, `/api/currencies/exchange-rates/`
- `POST /api/currencies/convert/` → `{"amount": "100.00", "from_currency": "USD", "to_currency": "PYG"}`

### Proveedores y Clientes (`/api/`)
- CRUD en `/api/proveedores/`, `/api/clientes/`

### Productos (`/api/`)
- CRUD en `/api/marcas/`, `/api/categorias/`, `/api/unidades-medida/`, `/api/impuestos/`
- CRUD en `/api/productos/` (listado liviano, detalle completo con componentes/lotes anidados)
- CRUD en `/api/componentes/` (BOM de combos/kits/compuestos)
- CRUD en `/api/lotes/`, `/api/series/`

### Inventario (`/api/inventory/`)
| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/inventory/movimientos/entrada/` | Registra una entrada de stock. |
| POST | `/api/inventory/movimientos/salida/` | Registra una salida de stock. |
| POST | `/api/inventory/movimientos/transferencia/` | Transferencia entre depósitos (sin alterar el costo). |
| POST | `/api/inventory/movimientos/ajuste/` | Ajuste manual positivo o negativo, con motivo. |
| POST | `/api/inventory/movimientos/conteo-fisico/` | Genera el ajuste automático por diferencia de conteo. |
| GET | `/api/inventory/kardex/?producto=<id>&deposito=<id>` | Historial completo de movimientos de un producto. |
| GET | `/api/inventory/valorizacion/?deposito=<id>` | Inventario valorizado (saldo x costo, por depósito/empresa). |
| GET (solo lectura) | `/api/inventory/saldos/`, `/api/inventory/capas-costo/`, `/api/inventory/movimientos/` | Consulta de saldos, capas FIFO/LIFO y kardex crudo. |
| CRUD | `/api/inventory/ubicaciones/` | Rack/pasillo/estantería/nivel dentro de un depósito. |

### Compras (`/api/purchases/`)
| Método | Endpoint | Descripción |
|---|---|---|
| CRUD | `/api/purchases/solicitudes/` | Solicitudes de compra. |
| CRUD | `/api/purchases/cotizaciones/` | Cotizaciones de proveedores. |
| GET | `/api/purchases/solicitudes/<id>/comparar-cotizaciones/` | Compara proveedores por costo/plazo/condiciones, ordenado por total. |
| POST | `/api/purchases/cotizaciones/<id>/crear-orden/` | Genera una Orden de Compra desde la cotización elegida. |
| CRUD | `/api/purchases/ordenes/` | Órdenes de compra (creación manual con items, o vía cotización). |
| POST | `/api/purchases/ordenes/recibir/` | Recepción de mercadería — descuenta contra `InventoryService.registrar_entrada`. |
| GET (solo lectura) | `/api/purchases/recepciones/` | Historial de recepciones. |
| CRUD | `/api/purchases/facturas-proveedor/` | Facturas recibidas de proveedores. |
| GET | `/api/purchases/proveedores/<id>/historial/` | Historial de órdenes y facturas de un proveedor. |

### Facturación (`/api/billing/`)
| Método | Endpoint | Descripción |
|---|---|---|
| GET (solo lectura) | `/api/billing/documentos/` | Lista/consulta de Facturas, NC, ND, Presupuestos y Remisiones (filtrable por `tipo_documento`, `estado`, `cliente`). |
| POST | `/api/billing/documentos/emitir/` | Emite cualquier tipo de documento. Si `afecta_inventario=true`, descuenta o repone stock automáticamente. |
| POST | `/api/billing/documentos/<id>/anular/` | Anula un documento; si afectaba inventario, genera el movimiento de reverso. |
| POST | `/api/billing/documentos/<id>/convertir-a-factura/` | Convierte un Presupuesto en Factura. |
| GET | `/api/billing/documentos/<id>/desglose-impuestos/` | Desglose de base/impuesto por tasa (IVA 10%/5%/exento), para el formato de factura electrónica. |

### CRM (`/api/crm/`)
| Método | Endpoint | Descripción |
|---|---|---|
| CRUD | `/api/crm/prospectos/` | Prospectos. |
| POST | `/api/crm/prospectos/<id>/convertir/` | Convierte un Prospecto en Cliente (migra sus contactos). |
| CRUD | `/api/crm/contactos/` | Contactos (de un Cliente o de un Prospecto). |
| CRUD | `/api/crm/etapas-pipeline/` | Etapas del pipeline de ventas, ordenadas por empresa. |
| CRUD | `/api/crm/oportunidades/` | Oportunidades de venta. |
| POST | `/api/crm/oportunidades/<id>/mover-etapa/` | Mueve una oportunidad a otra etapa (gana/pierde automáticamente según la etapa). |
| GET | `/api/crm/pipeline/resumen/` | Cantidad y valor de oportunidades abiertas, agrupado por etapa. |
| CRUD | `/api/crm/interacciones/` | Historial comercial / seguimiento. |

### Precios, Promociones y Cupones (`/api/pricing/`)
- CRUD en `/api/pricing/listas-precio/`, `/api/pricing/promociones/`, `/api/pricing/cupones/`

### Pedidos Web (`/api/orders/`)
| Método | Endpoint | Descripción |
|---|---|---|
| GET (solo lectura) | `/api/orders/pedidos/` | Lista/consulta de pedidos (uso interno). |
| POST | `/api/orders/pedidos/crear/` | Crea el pedido desde un carrito; resuelve precios+promos, aplica cupón, valida y reserva stock automáticamente. |
| POST | `/api/orders/pedidos/<id>/aprobar/` | Aprueba un pedido VALIDADO. |
| POST | `/api/orders/pedidos/<id>/rechazar/` | Rechaza y libera la reserva de stock. |
| POST | `/api/orders/pedidos/<id>/cancelar/` | Cancela (si aún no fue facturado) y libera la reserva. |
| POST | `/api/orders/pedidos/<id>/en-picking/` | Pasa a picking un pedido APROBADO. |
| POST | `/api/orders/pedidos/<id>/facturar/` | Genera la Factura real (`BillingService`) y descuenta stock real. |
| POST | `/api/orders/pedidos/<id>/despachar/` | Marca como despachado. |
| POST | `/api/orders/pedidos/<id>/entregar/` | Marca como entregado. |

### Portal de Clientes (`/api/customer-portal/`)
Autenticación **separada** de la interna — usar el token de
`/api/customer-portal/auth/login/`, no el de `/api/auth/login/`.

| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/customer-portal/auth/login/` | Login del cliente. |
| GET | `/api/customer-portal/auth/me/` | Perfil del usuario de portal autenticado. |
| POST | `/api/customer-portal/auth/cambiar-password/` | Cambia la contraseña propia. |
| POST | `/api/customer-portal/admin/provisionar-usuario/` | **Uso interno** (con token de empleado): da de alta una cuenta de portal para un Cliente. |
| GET | `/api/customer-portal/stock-disponible/` | Stock disponible para venta de los productos de la empresa del cliente. |
| GET | `/api/customer-portal/pedidos/` | Pedidos propios del cliente. |
| POST | `/api/customer-portal/pedidos/crear/` | El cliente solicita un nuevo pedido. |
| GET | `/api/customer-portal/pedidos/<id>/` | Seguimiento de un pedido puntual (incluye historial de estados). |
| POST | `/api/customer-portal/pedidos/<id>/cancelar/` | El cliente cancela su propio pedido. |
| GET | `/api/customer-portal/documentos/?tipo=FACTURA` | Facturas/presupuestos del cliente. |
| GET | `/api/customer-portal/estado-cuenta/` | Saldo pendiente y facturas impagas del cliente. |

### Caja y Tesorería (`/api/treasury/`)
| Método | Endpoint | Descripción |
|---|---|---|
| CRUD | `/api/treasury/cajas/` | Cajas registradoras. |
| GET (solo lectura) | `/api/treasury/aperturas/` | Aperturas de caja (con sus movimientos anidados y saldo esperado en efectivo). |
| POST | `/api/treasury/cajas/abrir/` | Abre una caja (falla si ya tiene una apertura activa sin cerrar). |
| POST | `/api/treasury/aperturas/<id>/cerrar/` | Cierra con arqueo (compara contado vs. esperado, registra la diferencia). |
| POST | `/api/treasury/movimientos/registrar/` | Ingreso/egreso genérico (gasto, retiro, depósito, etc.). |
| POST | `/api/treasury/movimientos/cobro-factura/` | Cobra una Factura (actualiza su `saldo_pendiente`). |
| POST | `/api/treasury/movimientos/pago-proveedor/` | Paga una Factura de Proveedor (actualiza su `saldo_pendiente` y `estado`). |
| CRUD | `/api/treasury/bancos/`, `/api/treasury/cuentas-bancarias/` | Bancos y cuentas. |
| GET (solo lectura) | `/api/treasury/movimientos-bancarios/` | Libro de movimientos bancarios. |
| POST | `/api/treasury/movimientos-bancarios/registrar/` | Depósito/retiro/transferencia en una cuenta bancaria. |

### Logística (`/api/logistics/`)
| Método | Endpoint | Descripción |
|---|---|---|
| CRUD | `/api/logistics/transportistas/`, `/api/logistics/vehiculos/`, `/api/logistics/rutas/` | Catálogos base. |
| GET (solo lectura) | `/api/logistics/ordenes-picking/` | Órdenes de picking. |
| POST | `/api/logistics/picking/iniciar/` | Inicia el picking de un pedido EN_PICKING. |
| POST | `/api/logistics/picking/<id>/completar/` | Registra qué se pickeó (cantidad + ubicación) y completa la orden. |
| POST | `/api/logistics/picking/<id>/packing/` | Genera el packing (bultos/peso/volumen) de un picking completado. |
| GET (solo lectura) | `/api/logistics/despachos/` | Despachos, con sus documentos asociados. |
| POST | `/api/logistics/despachos/crear/` | Crea un despacho con uno o más documentos de venta; marca los pedidos relacionados como DESPACHADO. |
| POST | `/api/logistics/despacho-documentos/<id>/entrega/` | Registra la entrega (o falla); marca el pedido relacionado como ENTREGADO. |

### Dashboard Ejecutivo (`/api/analytics/`)
Todos aceptan `?desde=YYYY-MM-DD&hasta=YYYY-MM-DD` (por defecto: desde el
día 1 del mes actual hasta hoy).

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/analytics/dashboard/` | Todos los indicadores principales en una sola llamada. |
| GET | `/api/analytics/ventas/resumen/` | Total de ventas, cantidad de facturas, ticket promedio. |
| GET | `/api/analytics/ventas/por-periodo/?agrupacion=DIA\|SEMANA\|MES` | Serie temporal para gráficos. |
| GET | `/api/analytics/ventas/comparativo/` | Período actual vs. el período anterior de igual duración. |
| GET | `/api/analytics/ventas/top-productos/?limite=10` | Productos más vendidos por monto. |
| GET | `/api/analytics/ventas/top-clientes/?limite=10` | Clientes con más compras por monto. |
| GET | `/api/analytics/compras/resumen/` | Total de compras del período (convertido a PYG). |
| GET | `/api/analytics/rentabilidad/` | Ventas netas, costo de ventas, margen bruto y margen %. |
| GET | `/api/analytics/inventario/resumen/` | Valor total de inventario y productos bajo stock mínimo. |
| GET | `/api/analytics/inventario/rotacion/` | Rotación aproximada (costo de ventas / valor de inventario actual). |

### Reportes (`/api/reports/`)
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/reports/kardex/excel/?producto=<id>&deposito=<id>` | Kardex completo de un producto en Excel. |
| GET | `/api/reports/inventario-valorizado/excel/?deposito=<id>` | Inventario valorizado en Excel. |
| GET | `/api/reports/ventas/excel/?desde=&hasta=` | Detalle de documentos de venta del período. |
| GET | `/api/reports/compras/excel/?desde=&hasta=` | Detalle de órdenes de compra del período. |
| GET | `/api/reports/clientes/excel/` | Listado de clientes. |
| GET | `/api/reports/proveedores/excel/` | Listado de proveedores. |
| GET | `/api/reports/rentabilidad/excel/?desde=&hasta=` | Rentabilidad por producto. |
| GET | `/api/reports/documentos/<id>/factura.pdf` | PDF de Factura/NC/ND/Presupuesto/Remisión, con desglose de IVA. |

### IA de Inventario (`/api/ai-engine/`)
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/ai-engine/demanda/proyeccion/?producto=<id>&meses_adelante=1` | Historial mensual + proyección + predicción a 3 meses. |
| GET | `/api/ai-engine/reposicion/sugerir-min-max/?producto=<id>&lead_time_dias=7` | Stock mínimo/máximo/seguridad sugeridos para un producto. |
| GET | `/api/ai-engine/reposicion/productos-a-reponer/` | Productos en o por debajo del stock mínimo. |
| GET | `/api/ai-engine/reposicion/sugerir-transferencias/` | Sugerencias de transferencia entre depósitos del mismo producto. |
| POST | `/api/ai-engine/reposicion/generar-orden-compra/` | Genera órdenes de compra BORRADOR agrupadas por proveedor principal. |
| GET | `/api/ai-engine/anomalias/sobre-stock/` | Productos con stock por encima de su máximo. |
| GET | `/api/ai-engine/anomalias/rotacion-lenta/?dias=90` | Productos con stock sin salidas en N días. |
| GET | `/api/ai-engine/anomalias/obsoletos/?dias=180` | Productos con stock sin ningún movimiento en N días. |
| GET | `/api/ai-engine/anomalias/criticos/` | Productos agotados (stock en cero). |
| GET | `/api/ai-engine/alertas-preventivas/` | Resumen consolidado de las cuatro anomalías anteriores. |

### Business Intelligence (`/api/bi/`)
| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/bi/abc/productos/?desde=&hasta=` | Clasificación ABC (Pareto 80/15/5) de productos por valor de venta. |
| GET | `/api/bi/abc/clientes/?desde=&hasta=` | Clasificación ABC de clientes por valor de compra. |
| GET | `/api/bi/clientes-en-declive/?umbral=20` | Clientes cuyas compras cayeron más del umbral % vs. el período anterior. |
| GET | `/api/bi/rotacion-por-categoria/` | Valor de inventario actual agrupado por categoría. |

### Copiloto del ERP (`/api/copilot/`)
| Método | Endpoint | Descripción |
|---|---|---|
| POST | `/api/copilot/preguntar/` | `{"pregunta": "..."}` → detecta la intención, consulta los servicios correspondientes y responde en lenguaje natural + datos estructurados. |
| GET | `/api/copilot/historial/` | Últimas 50 consultas propias (pregunta, intent detectado, respuesta). |

### Documentación de la API (Módulo 15)
| Endpoint | Descripción |
|---|---|
| `/api/docs/` | Swagger UI interactivo. |
| `/api/redoc/` | Redoc (documentación de solo lectura, más legible para referencia). |
| `/api/schema/` | Esquema OpenAPI crudo (YAML/JSON), por si se quiere generar un cliente. |

### Automatizaciones — Motor de Reglas (`/api/automation/`)
| Método | Endpoint | Descripción |
|---|---|---|
| CRUD | `/api/automation/reglas/` | Reglas de automatización (condiciones + acción). |
| GET (solo lectura) | `/api/automation/alertas/?leida=false` | Alertas generadas por reglas. |
| POST | `/api/automation/alertas/<id>/marcar-leida/` | Marca una alerta como leída. |
| GET (solo lectura) | `/api/automation/ejecuciones/` | Bitácora de cada evaluación de regla (cumplida o no). |
| POST | `/api/automation/evaluar/producto/` | Evalúa manualmente las reglas `AL_GUARDAR` de tipo Producto contra un producto puntual. |
| POST | `/api/automation/evaluar/pedido-web/` | Evalúa manualmente las reglas de tipo Pedido Web contra un pedido puntual (normalmente se dispara solo, vía señal, al crear el pedido). |

---

## Decisiones de diseño clave (para que el resto del ERP las respete)

1. **PYG es la moneda base.** Todo movimiento de stock, costo y reporte se
   valoriza internamente en PYG. `InventoryService` convierte automáticamente
   cualquier costo ingresado en otra moneda al registrar la entrada.
2. **Tasas de cambio históricas e inmutables.** Nunca se edita una tasa ya
   cargada; se carga una nueva con fecha más reciente.
3. **Roles con alcance.** Un mismo usuario puede tener distinto rol según
   la empresa/sucursal en la que esté operando (`RoleAssignment`).
4. **MFA con secreto cifrado.** El secreto TOTP nunca se guarda en texto
   plano (se cifra con Fernet derivada de `SECRET_KEY`).
5. **El Kardex es inmutable y es la fuente de verdad.** `MovimientoInventario`
   nunca se edita ni se borra. Un error se corrige con un movimiento de
   ajuste inverso (`InventoryService.registrar_ajuste`), igual que en un
   libro contable. `StockBalance` es solo un saldo denormalizado que se
   recalcula transaccionalmente junto a cada movimiento.
6. **Todo módulo que mueva stock (Compras, Facturación, y en el futuro
   Pedidos Web) lo hace exclusivamente a través de `InventoryService`**
   (`apps/inventory/services.py`), nunca escribiendo directo en
   `StockBalance`/`MovimientoInventario`. `PurchaseService.recibir_orden()`
   y `BillingService.emitir_documento()` son los puntos de conexión
   concretos en esta fase.
7. **El método de costeo es por producto** (`Producto.metodo_costeo`), no
   global, porque distintos productos del mismo negocio suelen necesitar
   métodos distintos.
8. **Facturación: precios netos + impuesto por línea.** `precio_unitario`
   en `DocumentoVentaItem` es neto (sin impuesto incluido); el impuesto se
   calcula aparte según `Producto.impuesto` (o uno indicado manualmente
   en la línea) y se suma al total. Esto permite desglosar IVA 10%/5%/exento
   por separado, como exige la facturación electrónica paraguaya.
9. **Anulación con reverso de inventario.** Anular una Factura/Remisión
   repone el stock (entrada al mismo costo que salió); anular una Nota de
   Crédito lo vuelve a descontar. Todo queda registrado en el Kardex con
   `documento_tipo="ANULACION"`, nunca se borra el movimiento original.
10. **Todo cálculo monetario usa `Decimal` con `ROUND_HALF_UP` explícito**
    en los puntos de redondeo (nunca `float`), para evitar diferencias de
    centésimos en reportes financieros.
11. **El Portal de Clientes tiene autenticación 100% separada de los
    empleados.** `PortalUser` no es el `AUTH_USER_MODEL` y nunca se
    mezcla con `request.empresa`/`request.sucursal` del middleware
    interno. `PortalJWTAuthentication` exige el claim `portal_user_id`
    (en vez de `user_id`), por lo que un token de portal jamás autentica
    contra un endpoint interno, y un token de empleado jamás autentica
    contra el portal — verificado con pruebas cruzadas en ambos sentidos.
12. **Las reservas de stock son "blandas" y no tocan el Kardex.**
    `StockReserva` (Módulo 4) solo resta de la "cantidad disponible para
    venta"; el movimiento real de inventario se genera recién al
    facturar el pedido. Esto evita que un carrito abandonado deje
    movimientos fantasma en el historial contable.
13. **El descuento de un cupón es un descuento de documento, no de
    línea.** `DocumentoVenta.descuento_global` se resta del total después
    de impuestos, pero **no** se redistribuye proporcionalmente entre
    líneas ni recalcula el IVA por línea — es una simplificación
    deliberada. Para una facturación electrónica 100% ajustada a la
    normativa de la SET con descuentos por línea, este cálculo necesita
    revisarse en la fase de Reportes/Facturación electrónica.
14. **Solo Tesorería actualiza saldos pendientes.** `TreasuryService.registrar_cobro_factura()`
    y `registrar_pago_proveedor()` son los únicos puntos del ERP que
    modifican `DocumentoVenta.saldo_pendiente` / `FacturaProveedor.saldo_pendiente`.
    Ningún otro módulo debe tocar esos campos directamente.
15. **Logística dispara las transiciones de `PedidoWeb`, no las duplica.**
    `LogisticsService.crear_despacho()` y `registrar_entrega()` llaman a
    `OrderService.marcar_despachado()`/`marcar_entregado()` en vez de
    tener su propia máquina de estados paralela, para que el estado del
    pedido y el estado logístico nunca queden desincronizados.
16. **El dashboard es de lectura en vivo, sin snapshot histórico.**
    `rotacion_inventario` usa el valor de inventario ACTUAL como
    aproximación del "inventario promedio del período" porque no hay
    snapshots diarios materializados — está documentado explícitamente
    en el código y es la limitación más importante a resolver si se
    necesita una rotación contablemente exacta.
17. **Los documentos fiscales en PDF usan estilo claro profesional, no
    el tema dark de la UI web.** Es lo esperado para un comprobante que
    se imprime o se envía a un cliente; el tema dark sigue aplicando a
    toda la interfaz web cuando se construya.
18. **La IA de inventario usa estadística clásica, no Machine Learning
    entrenado.** Promedio móvil + tendencia lineal para demanda,
    desviación estándar para stock de seguridad — son los métodos
    correctos para un ERP nuevo sin años de histórico todavía. El punto
    de extensión queda documentado en el código si más adelante se
    justifica un modelo real (Prophet, SARIMA).
19. **El Copiloto es un router de intenciones por palabras clave, no un
    LLM.** Cubre el catálogo de preguntas del enunciado original. El
    camino de upgrade a un LLM real (ej. la API de Anthropic, dado que
    Jorge ya tiene experiencia con MCP y Claude) es una decisión de
    producto deliberadamente no tomada acá — requiere una API key y
    conectividad saliente que Jorge debe habilitar él mismo.
20. **`stock_minimo`/`stock_maximo` son globales por producto, no por
    depósito.** Esto es así desde la Fase 1. La IA de reposición
    (`productos_para_reponer`) agrega el stock de TODOS los depósitos
    contra ese umbral global; `sugerir_transferencias`, en cambio, sí
    mira depósito por depósito usando esos mismos umbrales globales como
    referencia, para detectar desbalances entre sucursales. Si se
    necesitan umbrales distintos por depósito, hace falta un modelo
    `ProductoDeposito` nuevo — no existe todavía.
21. **El motor de reglas evalúa contra un "contexto" fijo por tipo de
    entidad, no contra cualquier campo de cualquier modelo.** Es la
    misma decisión de diseño que la IA de Inventario (#18): un motor 100%
    genérico exigiría introspección dinámica de todo el esquema, que es
    un proyecto en sí mismo. Agregar un nuevo campo disponible para las
    condiciones es agregar una clave al diccionario que devuelve
    `_construir_contexto_producto()`/`_construir_contexto_pedido_web()`
    en `apps/automation/services.py` — no requiere tocar el motor de
    evaluación en sí.
22. **Las reglas con `evaluar_en=PERIODICO` no se ejecutan solas.**
    Necesitan que el Celery worker + beat estén corriendo y que se cree
    la tarea periódica `evaluar_reglas_periodicas_todas_las_empresas`
    desde `/admin/django_celery_beat/periodictask/`. Las reglas con
    `evaluar_en=AL_GUARDAR` de tipo Pedido Web sí son automáticas (vía
    señal `post_save`); las de tipo Producto con `AL_GUARDAR` están
    disponibles para que cualquier módulo las dispare explícitamente
    (ej. después de un ajuste de inventario) pero no hay todavía una
    señal automática conectada a los movimientos de inventario.

---

## Próximas fases (según lo acordado)

1. ~~Fase 0 — Setup + Seguridad + Empresas + Monedas~~ ✅
2. ~~Fase 1 — Módulo 3 (Productos) + Módulo 4 (Inventario/Kardex con FIFO/LIFO/Promedio)~~ ✅
3. ~~Fase 2 — Módulo 9 (Compras) + Módulo 10 (Facturación)~~ ✅
4. ~~Fase 3 — Módulo 6/7/8 (CRM, Portal de Clientes, Pedidos Web)~~ ✅
5. ~~Fase 4 — Módulo 11/12 (Caja/Tesorería, Logística)~~ ✅
6. ~~Fase 5 — Módulo 13/14 (Dashboard, Reportes)~~ ✅
7. ~~Fase 6 — Módulo 5/17/19 (IA de inventario, BI, Copiloto)~~ ✅
8. ~~Fase 7 — Módulo 15/16 (Swagger/OpenAPI, motor de reglas)~~ ✅ (esta entrega — **cierra los 19 módulos del prompt original, sin pendientes de módulos**)

> **Estado del proyecto:** los 19 módulos del prompt original están
> construidos y probados de punta a punta. Lo que queda en la sección
> de "Pendiente" abajo son refinamientos dentro de módulos ya
> existentes (tests automatizados, CSV, snapshots históricos para
> rotación exacta, completar la documentación Swagger de los endpoints
> de acción, etc.), no módulos enteros sin construir.

## Pendiente (a definir contigo)

- Templates de login/MFA con el tema dark tech que usás en tus otros
  proyectos.
- ~~Tests automatizados (pytest)~~ ✅ — ver la sección "6. Tests" arriba.
  Los flujos que antes solo se habían probado a mano en el sandbox
  (login, MFA, conversión de monedas, costeo FIFO/LIFO/Promedio,
  facturación con multi-impuesto, el aislamiento del portal, el flujo
  completo de pedidos web, tesorería, logística, dashboard, reportes,
  IA de inventario, BI, copiloto y los 3 ejemplos del motor de reglas)
  ahora son ~165 tests de regresión real en `apps/*/tests.py`.
- Seguimiento en tiempo real de pedidos vía WebSocket (Django Channels):
  por ahora `HistorialEstadoPedido` permite seguimiento por polling, que
  cubre el requisito funcional, pero no hay push en tiempo real todavía.
- El descuento por cupón se aplica a nivel de documento, no por línea
  (ver decisión de diseño #13) — revisar si se necesita desglose por
  línea para cumplir 100% con el formato de factura electrónica.
- `Despacho`/`DespachoDocumento` asumen que cada `DocumentoVenta` tiene a
  lo sumo un `PedidoWeb` de origen (vía `pedido_origen`); si en el futuro
  una Factura pudiera originarse de más de un pedido, esa relación
  necesitaría revisarse.
- Conciliación bancaria automática (matching de extractos bancarios
  contra `MovimientoBancario`) — por ahora los movimientos bancarios se
  registran manualmente, uno por uno.
- Exportación a **CSV** (el prompt original la pedía junto a PDF/Excel):
  no se implementó todavía; es una extensión trivial de
  `apps/reports/services.py` ya que los datos están armados igual que
  para Excel.
- Documentación **Swagger/OpenAPI** del Módulo 15 (`drf-spectacular` +
  `/api/schema/` + `/api/docs/`) — los endpoints ya existen, falta la
  documentación autogenerada.
- **Módulo 16 — motor de reglas configurable** (SI/ENTONCES editable
  desde la UI, no hardcodeado en Python): es el único módulo del prompt
  original que no se construyó todavía. La IA de Inventario de la Fase 6
  ya cubre el contenido de esas reglas (stock bajo mínimo, sin
  movimiento > 180 días) pero como lógica fija, no como reglas que el
  usuario pueda crear/editar.
- Snapshots históricos de inventario valorizado (ej. cierre diario vía
  Celery Beat) para que `rotacion_inventario` (Fase 5) deje de ser una
  aproximación con el valor actual.
- La IA de inventario y el Copiloto fueron probados con datos sintéticos
  de 4 meses de historial — con datos reales de producción de Jorge
  conviene revalidar que las proyecciones de demanda tengan sentido
  (la fórmula de tendencia lineal puede sobre-reaccionar con muy pocos
  meses de historial real, como advierte el propio campo `metodo`
  cuando devuelve `"insuficiente_historial"`).
- Snapshots históricos de inventario valorizado (ej. cierre diario vía
  Celery Beat) para que `rotacion_inventario` deje de ser una
  aproximación con el valor actual y pase a ser un cálculo exacto sobre
  el inventario promedio real del período.
- La documentación Swagger/OpenAPI (Módulo 15) se genera correctamente
  para las ~200 rutas, pero ~90 vistas tipo `APIView` (las que reciben
  un body JSON validado a mano, en vez de heredar de `GenericAPIView`)
  aparecen con un esquema genérico "No response body" en vez de un
  request/response tipado. Es cosmético — los endpoints funcionan
  igual — pero si se quiere una documentación 100% completa, hay que
  agregar `@extend_schema(request=..., responses=...)` de
  `drf-spectacular` a esas vistas puntuales.
- El motor de reglas (Módulo 16) cubre `Producto` y `PedidoWeb` como
  tipos de entidad. Si más adelante se necesitan reglas sobre otras
  entidades (ej. `DocumentoVenta`, `Cliente`), hay que agregar su propio
  `_construir_contexto_*` en `apps/automation/services.py` — el motor de
  evaluación de condiciones en sí no necesita cambios.
- Las reglas `PERIODICO` necesitan que Jorge cree la tarea periódica en
  `/admin/django_celery_beat/periodictask/` apuntando a
  `apps.automation.tasks.evaluar_reglas_periodicas_todas_las_empresas`
  — no se auto-registra sola al crear una regla con ese modo.
- El dashboard no tiene caché ni push en tiempo real (Channels); cada
  llamada recalcula en vivo. Para una empresa con mucho volumen
  histórico podría valer la pena cachear los indicadores con una TTL
  corta.
- La suite de tests cubre la capa de servicios casi al 90%+, pero la
  capa de `views.py` (los endpoints REST en sí) tiene cobertura más
  baja (~30-60% según la app) — quedaron probados los críticos
  (login/MFA, portal, copiloto, provisión de usuarios) pero no cada
  endpoint CRUD genérico uno por uno. Si se necesita subir esa
  cobertura, lo más eficiente es agregar tests de integración por
  endpoint usando `auth_client` (fixture ya disponible en `conftest.py`).

