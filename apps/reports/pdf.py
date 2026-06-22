"""
PDF de documentos de venta (Módulo 14).

Resuelve el pendiente dejado en las Fases 2-3 ("falta la plantilla
visual" de los documentos de venta). Usa el `desglose_impuestos()` que
ya existía en `DocumentoVenta` desde la Fase 2.

Nota de diseño: a diferencia de la UI web (que sigue el tema dark tech
preferido), un documento fiscal impreso/descargado usa estilo claro
profesional estándar — es lo esperado para un comprobante que se
imprime o se envía a un cliente, y facilita la lectura en papel.
"""
try:
    from weasyprint import HTML
    WEASYPRINT_AVAILABLE = True
except OSError:
    HTML = None
    WEASYPRINT_AVAILABLE = False

FACTURA_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {{ size: A4; margin: 2cm; }}
    body {{ font-family: Helvetica, Arial, sans-serif; color: #1a1a1a; font-size: 11px; }}
    .header {{ display: flex; justify-content: space-between; border-bottom: 3px solid #1F2A37; padding-bottom: 12px; margin-bottom: 16px; }}
    .empresa-nombre {{ font-size: 18px; font-weight: bold; color: #1F2A37; }}
    .documento-tipo {{ text-align: right; }}
    .documento-tipo .titulo {{ font-size: 16px; font-weight: bold; color: #1F2A37; }}
    .documento-tipo .numero {{ font-size: 14px; font-family: monospace; }}
    .datos-cliente {{ margin-bottom: 16px; }}
    table.items {{ width: 100%; border-collapse: collapse; margin-bottom: 16px; }}
    table.items th {{ background-color: #1F2A37; color: white; padding: 6px 8px; text-align: left; font-size: 10px; }}
    table.items td {{ padding: 6px 8px; border-bottom: 1px solid #e0e0e0; }}
    table.items td.num {{ text-align: right; }}
    .totales {{ width: 280px; margin-left: auto; }}
    .totales table {{ width: 100%; }}
    .totales td {{ padding: 4px 8px; }}
    .totales .label {{ text-align: right; }}
    .totales .valor {{ text-align: right; font-family: monospace; }}
    .totales .total-final {{ font-weight: bold; font-size: 13px; border-top: 2px solid #1F2A37; }}
    .footer {{ margin-top: 24px; font-size: 9px; color: #666; border-top: 1px solid #ccc; padding-top: 8px; }}
</style>
</head>
<body>
    <div class="header">
        <div>
            <div class="empresa-nombre">{empresa_nombre}</div>
            <div>RUC: {empresa_ruc}</div>
            <div>{empresa_direccion}</div>
            <div>Timbrado N°: {timbrado_numero}</div>
        </div>
        <div class="documento-tipo">
            <div class="titulo">{tipo_documento_display}</div>
            <div class="numero">{numero}</div>
            <div>Fecha: {fecha_emision}</div>
        </div>
    </div>

    <div class="datos-cliente">
        <strong>Cliente:</strong> {cliente_nombre}<br>
        <strong>RUC/CI:</strong> {cliente_ruc}<br>
        <strong>Condición de venta:</strong> {condicion_venta}
    </div>

    <table class="items">
        <thead>
            <tr>
                <th>Código</th><th>Descripción</th><th class="num">Cant.</th>
                <th class="num">Precio Unit.</th><th class="num">Desc. %</th>
                <th class="num">Subtotal</th><th class="num">IVA</th><th class="num">Total</th>
            </tr>
        </thead>
        <tbody>
            {filas_items}
        </tbody>
    </table>

    <div class="totales">
        <table>
            <tr><td class="label">Subtotal:</td><td class="valor">{subtotal}</td></tr>
            <tr><td class="label">IVA:</td><td class="valor">{impuesto_total}</td></tr>
            <tr><td class="label">Descuento:</td><td class="valor">-{descuento_global}</td></tr>
            <tr class="total-final"><td class="label">TOTAL ({moneda}):</td><td class="valor">{total}</td></tr>
        </table>
    </div>

    <div class="footer">
        Documento generado por el sistema ERP Stock — {moneda} {tipo_cambio_nota}
    </div>
</body>
</html>
"""

FILA_ITEM_TEMPLATE = """
<tr>
    <td>{codigo}</td><td>{descripcion}</td><td class="num">{cantidad}</td>
    <td class="num">{precio_unitario}</td><td class="num">{descuento_porcentaje}</td>
    <td class="num">{subtotal_linea}</td><td class="num">{impuesto_linea}</td><td class="num">{total_linea}</td>
</tr>
"""


def _fmt(value, decimales=2):
    return f"{float(value):,.{decimales}f}"


def generar_factura_pdf(documento_venta) -> bytes:
    filas = []
    for item in documento_venta.items.select_related("producto").all():
        filas.append(FILA_ITEM_TEMPLATE.format(
            codigo=item.producto.codigo,
            descripcion=item.descripcion,
            cantidad=_fmt(item.cantidad, 4),
            precio_unitario=_fmt(item.precio_unitario),
            descuento_porcentaje=_fmt(item.descuento_porcentaje),
            subtotal_linea=_fmt(item.subtotal_linea),
            impuesto_linea=_fmt(item.impuesto_linea),
            total_linea=_fmt(item.total_linea),
        ))

    tipo_cambio_nota = ""
    if documento_venta.moneda.code != "PYG":
        tipo_cambio_nota = f"(TC: {_fmt(documento_venta.tipo_cambio_pyg, 2)} PYG, equivalente: {_fmt(documento_venta.total_pyg)} PYG)"

    html_content = FACTURA_TEMPLATE.format(
        empresa_nombre=documento_venta.empresa.nombre_comercial or documento_venta.empresa.razon_social,
        empresa_ruc=documento_venta.empresa.ruc,
        empresa_direccion=documento_venta.empresa.direccion or "",
        timbrado_numero=documento_venta.empresa.timbrado_numero or "-",
        tipo_documento_display=documento_venta.get_tipo_documento_display().upper(),
        numero=documento_venta.numero,
        fecha_emision=documento_venta.fecha_emision.strftime("%d/%m/%Y"),
        cliente_nombre=documento_venta.cliente.nombre_comercial or documento_venta.cliente.razon_social,
        cliente_ruc=documento_venta.cliente.ruc,
        condicion_venta=documento_venta.get_condicion_venta_display(),
        filas_items="".join(filas),
        subtotal=_fmt(documento_venta.subtotal),
        impuesto_total=_fmt(documento_venta.impuesto_total),
        descuento_global=_fmt(documento_venta.descuento_global),
        total=_fmt(documento_venta.total),
        moneda=documento_venta.moneda.code,
        tipo_cambio_nota=tipo_cambio_nota,
    )

    if not WEASYPRINT_AVAILABLE:
        raise RuntimeError("WeasyPrint no está disponible: instalá las librerías GTK en Windows (https://doc.courtbouillon.org/weasyprint/stable/first_steps.html#windows)")
    return HTML(string=html_content).write_pdf()
