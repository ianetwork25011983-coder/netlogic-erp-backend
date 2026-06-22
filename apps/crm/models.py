"""
Módulo 6 - CRM.

`Contacto` puede pertenecer a un `Cliente` ya existente o a un
`Prospecto` (exactamente uno de los dos, nunca ambos ni ninguno).
Lo mismo aplica a `Oportunidad` e `Interaccion`: el pipeline de ventas
funciona tanto para prospectos en negociación como para clientes ya
existentes con una nueva oportunidad (upsell/renovación).
"""
from django.core.exceptions import ValidationError
from django.db import models


class Prospecto(models.Model):
    ESTADO_NUEVO = "NUEVO"
    ESTADO_CONTACTADO = "CONTACTADO"
    ESTADO_CALIFICADO = "CALIFICADO"
    ESTADO_DESCARTADO = "DESCARTADO"
    ESTADO_CONVERTIDO = "CONVERTIDO"
    ESTADO_CHOICES = [
        (ESTADO_NUEVO, "Nuevo"),
        (ESTADO_CONTACTADO, "Contactado"),
        (ESTADO_CALIFICADO, "Calificado"),
        (ESTADO_DESCARTADO, "Descartado"),
        (ESTADO_CONVERTIDO, "Convertido a Cliente"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="prospectos")
    razon_social = models.CharField(max_length=200)
    nombre_comercial = models.CharField(max_length=200, blank=True)
    contacto_nombre = models.CharField(max_length=150, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    origen = models.CharField(max_length=100, blank=True, help_text="Referido, web, llamada fría, feria, etc.")
    estado = models.CharField(max_length=12, choices=ESTADO_CHOICES, default=ESTADO_NUEVO)
    responsable = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="prospectos_asignados", null=True, blank=True
    )
    notas = models.TextField(blank=True)
    cliente_convertido = models.OneToOneField(
        "customers.Cliente", on_delete=models.SET_NULL, related_name="prospecto_origen", null=True, blank=True
    )
    fecha_conversion = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Prospecto"
        verbose_name_plural = "Prospectos"
        ordering = ["-created_at"]

    def __str__(self):
        return self.nombre_comercial or self.razon_social


class Contacto(models.Model):
    cliente = models.ForeignKey(
        "customers.Cliente", on_delete=models.CASCADE, related_name="contactos", null=True, blank=True
    )
    prospecto = models.ForeignKey(
        Prospecto, on_delete=models.CASCADE, related_name="contactos", null=True, blank=True
    )
    nombre = models.CharField(max_length=150)
    cargo = models.CharField(max_length=100, blank=True)
    telefono = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    es_principal = models.BooleanField(default=False)
    notas = models.TextField(blank=True)

    class Meta:
        verbose_name = "Contacto"
        verbose_name_plural = "Contactos"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(cliente__isnull=False, prospecto__isnull=True)
                    | models.Q(cliente__isnull=True, prospecto__isnull=False)
                ),
                name="contacto_pertenece_a_cliente_o_prospecto_exclusivo",
            )
        ]

    def __str__(self):
        return f"{self.nombre} ({self.cliente or self.prospecto})"

    def clean(self):
        if bool(self.cliente_id) == bool(self.prospecto_id):
            raise ValidationError("El contacto debe pertenecer a exactamente un Cliente o un Prospecto, no ambos.")


class EtapaPipeline(models.Model):
    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="etapas_pipeline")
    nombre = models.CharField(max_length=50)
    orden = models.PositiveSmallIntegerField()
    es_ganada = models.BooleanField(default=False)
    es_perdida = models.BooleanField(default=False)
    active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Etapa de Pipeline"
        verbose_name_plural = "Etapas de Pipeline"
        ordering = ["empresa", "orden"]
        constraints = [
            models.UniqueConstraint(fields=["empresa", "orden"], name="unique_orden_etapa_por_empresa")
        ]

    def __str__(self):
        return self.nombre


class Oportunidad(models.Model):
    ESTADO_ABIERTA = "ABIERTA"
    ESTADO_GANADA = "GANADA"
    ESTADO_PERDIDA = "PERDIDA"
    ESTADO_CHOICES = [
        (ESTADO_ABIERTA, "Abierta"),
        (ESTADO_GANADA, "Ganada"),
        (ESTADO_PERDIDA, "Perdida"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="oportunidades")
    cliente = models.ForeignKey(
        "customers.Cliente", on_delete=models.CASCADE, related_name="oportunidades", null=True, blank=True
    )
    prospecto = models.ForeignKey(
        Prospecto, on_delete=models.CASCADE, related_name="oportunidades", null=True, blank=True
    )
    nombre = models.CharField(max_length=200)
    etapa_pipeline = models.ForeignKey(EtapaPipeline, on_delete=models.PROTECT, related_name="oportunidades")
    valor_estimado = models.DecimalField(max_digits=18, decimal_places=2, default=0)
    moneda = models.ForeignKey("currencies.Currency", on_delete=models.PROTECT, related_name="oportunidades")
    probabilidad_porcentaje = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    fecha_cierre_estimada = models.DateField(null=True, blank=True)
    responsable = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, related_name="oportunidades_asignadas", null=True, blank=True
    )
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default=ESTADO_ABIERTA)
    motivo_perdida = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Oportunidad"
        verbose_name_plural = "Oportunidades"
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(cliente__isnull=False, prospecto__isnull=True)
                    | models.Q(cliente__isnull=True, prospecto__isnull=False)
                ),
                name="oportunidad_pertenece_a_cliente_o_prospecto_exclusivo",
            )
        ]

    def __str__(self):
        return f"{self.nombre} - {self.get_estado_display()}"

    def clean(self):
        if bool(self.cliente_id) == bool(self.prospecto_id):
            raise ValidationError("La oportunidad debe pertenecer a exactamente un Cliente o un Prospecto, no ambos.")


class Interaccion(models.Model):
    """Historial comercial / seguimiento: llamadas, emails, reuniones, notas."""

    TIPO_LLAMADA = "LLAMADA"
    TIPO_EMAIL = "EMAIL"
    TIPO_REUNION = "REUNION"
    TIPO_WHATSAPP = "WHATSAPP"
    TIPO_NOTA = "NOTA"
    TIPO_CHOICES = [
        (TIPO_LLAMADA, "Llamada"),
        (TIPO_EMAIL, "Email"),
        (TIPO_REUNION, "Reunión"),
        (TIPO_WHATSAPP, "WhatsApp"),
        (TIPO_NOTA, "Nota"),
    ]

    empresa = models.ForeignKey("companies.Empresa", on_delete=models.CASCADE, related_name="interacciones")
    cliente = models.ForeignKey(
        "customers.Cliente", on_delete=models.CASCADE, related_name="interacciones", null=True, blank=True
    )
    prospecto = models.ForeignKey(
        Prospecto, on_delete=models.CASCADE, related_name="interacciones", null=True, blank=True
    )
    oportunidad = models.ForeignKey(
        Oportunidad, on_delete=models.SET_NULL, related_name="interacciones", null=True, blank=True
    )
    tipo = models.CharField(max_length=10, choices=TIPO_CHOICES)
    descripcion = models.TextField()
    usuario = models.ForeignKey("accounts.User", on_delete=models.SET_NULL, related_name="interacciones", null=True)
    fecha = models.DateTimeField(auto_now_add=True)
    fecha_proxima_accion = models.DateTimeField(null=True, blank=True, help_text="Para seguimiento: cuándo volver a contactar")
    completada = models.BooleanField(default=True, help_text="False si es un seguimiento programado a futuro, aún pendiente")

    class Meta:
        verbose_name = "Interacción"
        verbose_name_plural = "Interacciones"
        ordering = ["-fecha"]
        indexes = [
            models.Index(fields=["cliente", "-fecha"]),
            models.Index(fields=["prospecto", "-fecha"]),
            models.Index(fields=["fecha_proxima_accion"]),
        ]

    def __str__(self):
        return f"{self.get_tipo_display()} - {self.cliente or self.prospecto} ({self.fecha:%Y-%m-%d})"
