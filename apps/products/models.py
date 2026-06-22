"""
Módulo 3 - Maestro de Productos.

Decisiones de diseño:
- Una sola entidad `Producto` cubre PRODUCTO, SERVICIO, COMBO, KIT y
  COMPUESTO; el campo `tipo` cambia el comportamiento (un SERVICIO no
  descuenta stock, un COMBO/KIT/COMPUESTO tiene una lista de componentes
  vía `ProductoComponente`, que funciona como BOM - bill of materials).
- `Categoria` es auto-referenciada (parent) en lugar de tener un modelo
  separado de Subcategoría: una subcategoría es simplemente una Categoria
  con `parent` distinto de null.
- El método de costeo (FIFO/LIFO/Promedio Ponderado) se define por
  producto, porque distintos productos de un mismo negocio suelen
  necesitar métodos distintos (ej. productos perecederos casi siempre
  FIFO, commodities a veces Promedio).
- `stock_minimo`/`stock_maximo`/`stock_seguridad` quedan como valores base
  configurables a mano en esta fase. El Módulo 5 (IA de Inventario, fase
  posterior) los podrá sugerir/sobreescribir por depósito.
"""
from django.core.exceptions import ValidationError
from django.db import models


class Marca(models.Model):
    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="marcas")
    nombre = models.CharField(max_length=100)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Marca"
        verbose_name_plural = "Marcas"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["empresa", "nombre"], name="unique_marca_por_empresa")
        ]

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="categorias")
    nombre = models.CharField(max_length=100)
    parent = models.ForeignKey(
        "self", on_delete=models.CASCADE, related_name="subcategorias", null=True, blank=True,
        help_text="Dejar vacío si es una categoría raíz; completar para que sea una subcategoría",
    )
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Categoría"
        verbose_name_plural = "Categorías"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["empresa", "parent", "nombre"], nulls_distinct=False,
                name="unique_categoria_por_empresa_y_parent",
            )
        ]

    def __str__(self):
        if self.parent:
            return f"{self.parent} > {self.nombre}"
        return self.nombre

    def clean(self):
        if self.parent_id and self.parent_id == self.pk:
            raise ValidationError("Una categoría no puede ser su propio padre.")


class UnidadMedida(models.Model):
    codigo = models.CharField(max_length=10, unique=True, help_text="UN, KG, LT, MT, CJ, etc.")
    nombre = models.CharField(max_length=50)
    permite_decimales = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Unidad de Medida"
        verbose_name_plural = "Unidades de Medida"
        ordering = ["codigo"]

    def __str__(self):
        return self.codigo


class Impuesto(models.Model):
    nombre = models.CharField(max_length=50, help_text="IVA 10%, IVA 5%, Exento, etc.")
    tasa_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, help_text="10.00 para IVA 10%")
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Impuesto"
        verbose_name_plural = "Impuestos"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    TIPO_PRODUCTO = "PRODUCTO"
    TIPO_SERVICIO = "SERVICIO"
    TIPO_COMBO = "COMBO"
    TIPO_KIT = "KIT"
    TIPO_COMPUESTO = "COMPUESTO"
    TIPO_CHOICES = [
        (TIPO_PRODUCTO, "Producto"),
        (TIPO_SERVICIO, "Servicio"),
        (TIPO_COMBO, "Combo"),
        (TIPO_KIT, "Kit"),
        (TIPO_COMPUESTO, "Producto Compuesto"),
    ]
    TIPOS_CON_COMPONENTES = (TIPO_COMBO, TIPO_KIT, TIPO_COMPUESTO)
    TIPOS_QUE_DESCUENTAN_STOCK = (TIPO_PRODUCTO, TIPO_COMBO, TIPO_KIT, TIPO_COMPUESTO)

    METODO_FIFO = "FIFO"
    METODO_LIFO = "LIFO"
    METODO_PROMEDIO = "PROMEDIO"
    METODO_CHOICES = [
        (METODO_FIFO, "FIFO - Primero en entrar, primero en salir"),
        (METODO_LIFO, "LIFO - Último en entrar, primero en salir"),
        (METODO_PROMEDIO, "Promedio Ponderado"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="productos")
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES, default=TIPO_PRODUCTO)

    codigo = models.CharField(max_length=30, help_text="Código interno del producto")
    sku = models.CharField(max_length=50, blank=True)
    codigo_barras = models.CharField(max_length=50, blank=True)
    qr_data = models.CharField(
        max_length=255, blank=True,
        help_text="Contenido codificado en el QR (por defecto, el código interno)",
    )

    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True)

    marca = models.ForeignKey(Marca, on_delete=models.SET_NULL, null=True, blank=True, related_name="productos")
    categoria = models.ForeignKey(
        Categoria, on_delete=models.SET_NULL, null=True, blank=True, related_name="productos"
    )
    proveedor_principal = models.ForeignKey(
        "suppliers.Proveedor", on_delete=models.SET_NULL, null=True, blank=True, related_name="productos"
    )
    unidad_medida = models.ForeignKey(UnidadMedida, on_delete=models.PROTECT, related_name="productos")
    impuesto = models.ForeignKey(Impuesto, on_delete=models.SET_NULL, null=True, blank=True, related_name="productos")

    moneda_costo = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT, related_name="productos_costo"
    )
    costo = models.DecimalField(max_digits=18, decimal_places=6, default=0)
    moneda_precio = models.ForeignKey(
        "currencies.Currency", on_delete=models.PROTECT, related_name="productos_precio"
    )
    precio = models.DecimalField(max_digits=18, decimal_places=6, default=0)

    peso_kg = models.DecimalField(max_digits=10, decimal_places=3, null=True, blank=True)
    volumen_m3 = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    imagen = models.ImageField(upload_to="productos/", null=True, blank=True)

    controla_lote = models.BooleanField(default=False)
    controla_serie = models.BooleanField(default=False)
    controla_vencimiento = models.BooleanField(default=False)
    metodo_costeo = models.CharField(max_length=10, choices=METODO_CHOICES, default=METODO_PROMEDIO)

    stock_minimo = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    stock_maximo = models.DecimalField(max_digits=14, decimal_places=3, default=0)
    stock_seguridad = models.DecimalField(max_digits=14, decimal_places=3, default=0)

    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ["nombre"]
        constraints = [
            models.UniqueConstraint(fields=["empresa", "codigo"], name="unique_producto_codigo_por_empresa"),
        ]
        indexes = [
            models.Index(fields=["empresa", "sku"]),
            models.Index(fields=["empresa", "codigo_barras"]),
        ]

    def __str__(self):
        return f"{self.codigo} - {self.nombre}"

    def clean(self):
        if self.controla_serie and self.controla_lote:
            raise ValidationError(
                "Un producto no puede controlarse simultáneamente por lote y por serie; "
                "elija una sola estrategia de trazabilidad."
            )
        if self.controla_vencimiento and not self.controla_lote:
            raise ValidationError(
                "El control de vencimiento requiere activar también el control por lote "
                "(la fecha de vencimiento se registra a nivel de lote)."
            )

    @property
    def descuenta_stock(self) -> bool:
        return self.tipo in self.TIPOS_QUE_DESCUENTAN_STOCK

    @property
    def usa_componentes(self) -> bool:
        return self.tipo in self.TIPOS_CON_COMPONENTES


class ProductoComponente(models.Model):
    """
    Línea de BOM (bill of materials): qué componentes y en qué cantidad
    integran un Producto de tipo COMBO/KIT/COMPUESTO.
    """

    producto_padre = models.ForeignKey(
        Producto, on_delete=models.CASCADE, related_name="componentes",
        limit_choices_to={"tipo__in": Producto.TIPOS_CON_COMPONENTES},
    )
    producto_componente = models.ForeignKey(
        Producto, on_delete=models.PROTECT, related_name="usado_en_combos",
    )
    cantidad = models.DecimalField(max_digits=14, decimal_places=3)

    class Meta:
        verbose_name = "Componente de Producto"
        verbose_name_plural = "Componentes de Producto"
        constraints = [
            models.UniqueConstraint(
                fields=["producto_padre", "producto_componente"], name="unique_componente_por_padre"
            )
        ]

    def __str__(self):
        return f"{self.producto_padre} <- {self.cantidad} x {self.producto_componente}"

    def clean(self):
        if self.producto_padre_id == self.producto_componente_id:
            raise ValidationError("Un producto no puede ser componente de sí mismo.")
        if self.producto_padre_id and self.producto_padre.tipo not in Producto.TIPOS_CON_COMPONENTES:
            raise ValidationError("Solo productos de tipo COMBO, KIT o COMPUESTO pueden tener componentes.")


class Lote(models.Model):
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="lotes")
    numero_lote = models.CharField(max_length=50)
    proveedor = models.ForeignKey(
        "suppliers.Proveedor", on_delete=models.SET_NULL, null=True, blank=True, related_name="lotes"
    )
    fecha_fabricacion = models.DateField(null=True, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Lote"
        verbose_name_plural = "Lotes"
        ordering = ["fecha_vencimiento", "fecha_ingreso"]
        constraints = [
            models.UniqueConstraint(fields=["producto", "numero_lote"], name="unique_lote_por_producto")
        ]

    def __str__(self):
        return f"{self.producto.codigo} - Lote {self.numero_lote}"

    def clean(self):
        if self.producto_id and not self.producto.controla_lote:
            raise ValidationError("Este producto no tiene activado el control por lote.")


class Serie(models.Model):
    ESTADO_DISPONIBLE = "DISPONIBLE"
    ESTADO_RESERVADO = "RESERVADO"
    ESTADO_VENDIDO = "VENDIDO"
    ESTADO_DEFECTUOSO = "DEFECTUOSO"
    ESTADO_CHOICES = [
        (ESTADO_DISPONIBLE, "Disponible"),
        (ESTADO_RESERVADO, "Reservado"),
        (ESTADO_VENDIDO, "Vendido"),
        (ESTADO_DEFECTUOSO, "Defectuoso"),
    ]

    producto = models.ForeignKey(Producto, on_delete=models.CASCADE, related_name="series")
    numero_serie = models.CharField(max_length=100)
    lote = models.ForeignKey(Lote, on_delete=models.SET_NULL, null=True, blank=True, related_name="series")
    deposito_actual = models.ForeignKey(
        "companies.Deposito", on_delete=models.SET_NULL, null=True, blank=True, related_name="series"
    )
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=ESTADO_DISPONIBLE)
    fecha_ingreso = models.DateTimeField(auto_now_add=True)
    fecha_egreso = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Serie"
        verbose_name_plural = "Series"
        constraints = [
            models.UniqueConstraint(fields=["producto", "numero_serie"], name="unique_serie_por_producto")
        ]

    def __str__(self):
        return f"{self.producto.codigo} - S/N {self.numero_serie}"

    def clean(self):
        if self.producto_id and not self.producto.controla_serie:
            raise ValidationError("Este producto no tiene activado el control por serie.")
