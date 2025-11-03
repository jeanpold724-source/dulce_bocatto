# accounts/views_reportes.py
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
import csv

from django.http import HttpResponse
from django.shortcuts import render
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.utils.timezone import now

# Decorador de permisos propio (ajústalo si no lo usas)
from .permissions import requiere_permiso

# Si no usas estos, puedes quitarlos
from django.db.models import Sum  # noqa: F401
from .models_db import Compra     # noqa: F401


# ================================================================
# Helpers comunes
# ================================================================
def _build_order_mysql(sort: str, direction: str) -> str:
    """
    ORDER BY seguro (whitelist) para historial de clientes.
    Campos visibles: cliente | creado | total | estado
    Simula NULLS LAST en orden ASC.
    """
    direction = (direction or "desc").lower()
    if direction not in ("asc", "desc"):
        direction = "desc"

    allowed = {
        "cliente": "cliente",
        "creado": "p.created_at",
        "total": "p.total",
        "estado": "p.estado",
    }
    col = allowed.get((sort or "").lower(), "p.created_at")

    if direction == "asc":
        return f"CASE WHEN {col} IS NULL THEN 1 ELSE 0 END, {col} ASC"
    return f"{col} DESC"


def _parse_date(s: str | None):
    if not s:
        return None
    s = s.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            pass
    return None


# ================================================================
# CU18 – Historial de compras de clientes
# ================================================================
def _fetch_historial(q: str | None, d1: str | None, d2: str | None, order_sql: str):
    """
    Trae los pedidos CONFIRMADO con totales y pagado agregado.
    Filtro por nombre/email (LIKE) y rango de fechas en created_at.
    """
    where = ["p.estado = 'CONFIRMADO'"]
    params: list = []

    if q:
        where.append(
            "(u.email LIKE CONCAT('%%', %s, '%%') OR u.nombre LIKE CONCAT('%%', %s, '%%'))"
        )
        params.extend([q, q])

    if d1:
        where.append("DATE(p.created_at) >= %s")
        params.append(d1)
    if d2:
        where.append("DATE(p.created_at) <= %s")
        params.append(d2)

    where_sql = " AND ".join(where) if where else "1=1"

    sql = f"""
        SELECT
            p.id AS pedido_id,
            DATE_FORMAT(p.created_at, '%%Y-%%m-%%d %%H:%%i') AS creado,
            u.email AS cliente_email,
            COALESCE(NULLIF(TRIM(c.nombre), ''), NULLIF(TRIM(u.nombre), ''), u.email) AS cliente,
            p.total AS total,
            p.estado AS estado,
            COALESCE(SUM(pg.monto), 0) AS pagado
        FROM pedido p
        LEFT JOIN cliente c ON c.id = p.cliente_id
        LEFT JOIN usuario u ON u.id = c.usuario_id
        LEFT JOIN pago pg   ON pg.pedido_id = p.id
        WHERE {where_sql}
        GROUP BY p.id, creado, cliente_email, cliente, total, estado
        ORDER BY {order_sql}
        LIMIT 500
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@login_required
@requiere_permiso("PEDIDO_READ")
def historial_clientes(request):
    q  = (request.GET.get("q") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None

    sort = request.GET.get("sort", "creado")
    direction = request.GET.get("dir", "desc")
    order_sql = _build_order_mysql(sort, direction)

    rows = _fetch_historial(q, d1, d2, order_sql)

    total_pedidos = len(rows)  # una fila por pedido
    total_monto   = sum(Decimal(r["total"] or 0) for r in rows)

    return render(
        request,
        "accounts/historial_clientes.html",
        {
            "rows": rows,
            "q": q or "",
            "d1": d1 or "",
            "d2": d2 or "",
            "sort": sort,
            "dir": direction,
            "total_clientes": len({r["cliente_email"] for r in rows if r.get("cliente_email")}),
            "total_pedidos": total_pedidos,
            "total_monto": total_monto,
        },
    )


@login_required
@requiere_permiso("PEDIDO_READ")
def historial_clientes_csv(request):
    q  = (request.GET.get("q") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None

    order_sql = _build_order_mysql("creado", "desc")
    rows = _fetch_historial(q, d1, d2, order_sql)

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="historial_clientes.csv"'
    w = csv.writer(resp)
    w.writerow(["Pedido", "Creado", "Cliente", "Email", "Total (Bs.)", "Estado", "Pagado (Bs.)"])
    for r in rows:
        w.writerow([
            r.get("pedido_id", ""),
            r.get("creado", ""),
            r.get("cliente", "") or "",
            r.get("cliente_email", "") or "",
            f"{Decimal(r.get('total') or 0):.2f}",
            r.get("estado", "") or "",
            f"{Decimal(r.get('pagado') or 0):.2f}",
        ])
    return resp


@login_required
@requiere_permiso("PEDIDO_READ")
def historial_clientes_html(request):
    q  = (request.GET.get("q") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None

    order_sql = _build_order_mysql("creado", "desc")
    rows = _fetch_historial(q, d1, d2, order_sql)

    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>Historial de pedidos</title>",
        "<style>table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px}th{background:#f6f6f6;text-align:left}</style>",
        "</head><body>",
        "<h2>Historial de pedidos</h2>",
        f"<p>Filtro q: {q or '-'} | Desde: {d1 or '-'} | Hasta: {d2 or '-'}</p>",
        "<table><thead><tr>",
        "<th>#</th><th>Creado</th><th>Cliente</th><th>Email</th><th>Total (Bs.)</th><th>Estado</th><th>Pagado (Bs.)</th>",
        "</tr></thead><tbody>",
    ]
    for r in rows:
        html.append(
            "<tr>"
            f"<td>{r.get('pedido_id','')}</td>"
            f"<td>{r.get('creado','')}</td>"
            f"<td>{(r.get('cliente') or '')}</td>"
            f"<td>{(r.get('cliente_email') or '')}</td>"
            f"<td>{Decimal(r.get('total') or 0):.2f}</td>"
            f"<td>{(r.get('estado') or '')}</td>"
            f"<td>{Decimal(r.get('pagado') or 0):.2f}</td>"
            "</tr>"
        )
    html.append("</tbody></table></body></html>")

    resp = HttpResponse("".join(html), content_type="text/html; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="historial_clientes.html"'
    return resp


@login_required
@requiere_permiso("PEDIDO_READ")
def historial_clientes_pdf(request):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
    except Exception:
        return HttpResponse(
            "Exportación a PDF no disponible: instala 'reportlab' (pip install reportlab).",
            content_type="text/plain; charset=utf-8",
            status=200,
        )

    q  = (request.GET.get("q") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None

    order_sql = _build_order_mysql("creado", "desc")
    rows = _fetch_historial(q, d1, d2, order_sql)

    resp = HttpResponse(content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="historial_clientes.pdf"'

    p = canvas.Canvas(resp, pagesize=landscape(A4))
    width, height = landscape(A4)
    x = 2 * cm
    y = height - 2 * cm

    p.setFont("Helvetica-Bold", 14)
    p.drawString(x, y, "Historial de pedidos")
    y -= 0.8 * cm
    p.setFont("Helvetica", 10)
    p.drawString(x, y, f"Filtro q: {q or '-'}  |  Desde: {d1 or '-'}  |  Hasta: {d2 or '-'}")
    y -= 1.0 * cm

    headers = ["#", "Creado", "Cliente", "Email", "Total (Bs.)", "Estado", "Pagado (Bs.)"]
    col_x = [x, x + 3.5*cm, x + 9.5*cm, x + 17*cm, x + 22*cm, x + 26*cm, x + 31*cm]

    p.setFont("Helvetica-Bold", 10)
    for i, h in enumerate(headers):
        p.drawString(col_x[i], y, h)
    y -= 0.6 * cm
    p.setFont("Helvetica", 10)

    for r in rows:
        if y < 1.5 * cm:
            p.showPage()
            p.setFont("Helvetica-Bold", 10)
            for i, h in enumerate(headers):
                p.drawString(col_x[i], height - 2 * cm, h)
            p.setFont("Helvetica", 10)
            y = height - 2.6 * cm

        vals = [
            str(r.get("pedido_id","")),
            r.get("creado",""),
            (r.get("cliente") or ""),
            (r.get("cliente_email") or ""),
            f"{Decimal(r.get('total') or 0):.2f}",
            (r.get("estado") or ""),
            f"{Decimal(r.get('pagado') or 0):.2f}",
        ]
        for i, v in enumerate(vals):
            p.drawString(col_x[i], y, v[:60])
        y -= 0.55 * cm

    p.showPage()
    p.save()
    return resp


# ================================================================
# CU23 – Reporte de ventas diarias
# ================================================================
def _build_order_mysql_ventas(sort: str, direction: str) -> str:
    direction = (direction or "desc").lower()
    if direction not in ("asc", "desc"):
        direction = "desc"

    allowed = {
        "fecha": "fecha",
        "pedidos": "pedidos",
        "total": "total",
        "pagado": "pagado",
        "diferencia": "diferencia",
    }
    col = allowed.get((sort or "").lower(), "fecha")

    if direction == "asc":
        return f"CASE WHEN {col} IS NULL THEN 1 ELSE 0 END, {col} ASC"
    return f"{col} DESC"


def _fetch_ventas_diarias(d1: str | None, d2: str | None, order_sql: str):
    params: list = []
    where = ["p.estado IN ('CONFIRMADO','ENTREGADO')"]

    if d1:
        where.append("DATE(p.created_at) >= %s")
        params.append(d1)
    if d2:
        where.append("DATE(p.created_at) <= %s")
        params.append(d2)

    where_sql = " AND ".join(where) if where else "1=1"

    sql = f"""
        SELECT
            DATE(p.created_at) AS fecha,
            COUNT(DISTINCT p.id) AS pedidos,
            COALESCE(SUM(p.total), 0) AS total,
            COALESCE(SUM(pg.monto), 0) AS pagado,
            COALESCE(SUM(p.total), 0) - COALESCE(SUM(pg.monto), 0) AS diferencia
        FROM pedido p
        LEFT JOIN pago pg ON pg.pedido_id = p.id
        WHERE {where_sql}
        GROUP BY DATE(p.created_at)
        ORDER BY {order_sql}
        LIMIT 1000
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@login_required
@requiere_permiso("PEDIDO_READ")
def ventas_diarias(request):
    d1 = (request.GET.get("d1") or "").strip()
    d2 = (request.GET.get("d2") or "").strip()

    sort = request.GET.get("sort", "fecha")
    direction = request.GET.get("dir", "desc")
    order_sql = _build_order_mysql_ventas(sort, direction)

    rows = _fetch_ventas_diarias(d1, d2, order_sql)

    total_pedidos = sum(r["pedidos"] or 0 for r in rows)
    total_total   = sum(Decimal(r["total"] or 0) for r in rows)
    total_pagado  = sum(Decimal(r["pagado"] or 0) for r in rows)
    total_diff    = sum(Decimal(r["diferencia"] or 0) for r in rows)

    def _next_dir(col: str) -> str:
        return "asc" if (direction == "desc" or sort != col) else "desc"

    context = {
        "rows": rows,
        "d1": d1, "d2": d2,
        "sort": sort, "dir": direction,
        "total_pedidos": total_pedidos,
        "total_total": total_total,
        "total_pagado": total_pagado,
        "total_diff": total_diff,
        "next_dir_fecha": _next_dir("fecha"),
        "next_dir_ped": _next_dir("pedidos"),
        "next_dir_total": _next_dir("total"),
        "next_dir_pag": _next_dir("pagado"),
        "next_dir_diff": _next_dir("diferencia"),
    }
    return render(request, "accounts/ventas_diarias.html", context)


@login_required
@requiere_permiso("PEDIDO_READ")
def ventas_diarias_csv(request):
    d1 = (request.GET.get("d1") or "").strip()
    d2 = (request.GET.get("d2") or "").strip()
    order_sql = _build_order_mysql_ventas(
        request.GET.get("sort", "fecha"),
        request.GET.get("dir", "desc"),
    )
    rows = _fetch_ventas_diarias(d1, d2, order_sql)

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="ventas_diarias.csv"'
    w = csv.writer(resp)
    w.writerow(["Fecha", "Pedidos", "Total (Bs.)", "Pagado (Bs.)", "Diferencia (Bs.)"])
    for r in rows:
        w.writerow([
            str(r["fecha"] or ""),
            r["pedidos"] or 0,
            f"{Decimal(r['total'] or 0):.2f}",
            f"{Decimal(r['pagado'] or 0):.2f}",
            f"{Decimal(r['diferencia'] or 0):.2f}",
        ])
    return resp


@login_required
@requiere_permiso("PEDIDO_READ")
def ventas_diarias_html(request):
    d1 = (request.GET.get("d1") or "").strip()
    d2 = (request.GET.get("d2") or "").strip()
    order_sql = _build_order_mysql_ventas(
        request.GET.get("sort", "fecha"),
        request.GET.get("dir", "desc"),
    )
    rows = _fetch_ventas_diarias(d1, d2, order_sql)

    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>Ventas diarias</title>",
        "<style>table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px}th{background:#f6f6f6;text-align:left}</style>",
        "</head><body>",
        "<h2>Reporte de ventas diarias</h2>",
        f"<p>Desde: {d1 or '-'} &nbsp; Hasta: {d2 or '-'}</p>",
        "<table><thead><tr>",
        "<th>Fecha</th><th>Pedidos</th><th>Total (Bs.)</th><th>Pagado (Bs.)</th><th>Diferencia (Bs.)</th>",
        "</tr></thead><tbody>",
    ]
    for r in rows:
        html.append(
            f"<tr><td>{r['fecha']}</td><td>{r['pedidos']}</td>"
            f"<td>{Decimal(r['total'] or 0):.2f}</td>"
            f"<td>{Decimal(r['pagado'] or 0):.2f}</td>"
            f"<td>{Decimal(r['diferencia'] or 0):.2f}</td></tr>"
        )
    html.append("</tbody></table></body></html>")
    return HttpResponse("".join(html), content_type="text/html; charset=utf-8")


@login_required
@requiere_permiso("PEDIDO_READ")
def ventas_diarias_pdf(request):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
    except Exception:
        return HttpResponse(
            "Exportación a PDF no disponible: instala 'reportlab'.",
            content_type="text/plain; charset=utf-8",
            status=200,
        )

    d1 = (request.GET.get("d1") or "").strip()
    d2 = (request.GET.get("d2") or "").strip()
    order_sql = _build_order_mysql_ventas(
        request.GET.get("sort", "fecha"),
        request.GET.get("dir", "desc"),
    )
    rows = _fetch_ventas_diarias(d1, d2, order_sql)

    resp = HttpResponse(content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="ventas_diarias.pdf"'

    p = canvas.Canvas(resp, pagesize=landscape(A4))
    width, height = landscape(A4)
    x = 2 * cm
    y = height - 2 * cm

    p.setFont("Helvetica-Bold", 14)
    p.drawString(x, y, "Reporte de ventas diarias")
    y -= 0.8 * cm
    p.setFont("Helvetica", 10)
    p.drawString(x, y, f"Desde: {d1 or '-'} | Hasta: {d2 or '-'}")
    y -= 1.0 * cm

    headers = ["Fecha", "Pedidos", "Total (Bs.)", "Pagado (Bs.)", "Dif. (Bs.)"]
    col_x = [x, x + 6*cm, x + 10*cm, x + 16*cm, x + 22*cm]

    p.setFont("Helvetica-Bold", 10)
    for i, h in enumerate(headers):
        p.drawString(col_x[i], y, h)
    y -= 0.6 * cm
    p.setFont("Helvetica", 10)

    for r in rows:
        if y < 1.5 * cm:
            p.showPage()
            p.setFont("Helvetica-Bold", 10)
            for i, h in enumerate(headers):
                p.drawString(col_x[i], height - 2 * cm, h)
            p.setFont("Helvetica", 10)
            y = height - 2.6 * cm

        vals = [
            str(r["fecha"] or ""),
            str(r["pedidos"] or 0),
            f"{Decimal(r['total'] or 0):.2f}",
            f"{Decimal(r['pagado'] or 0):.2f}",
            f"{Decimal(r['diferencia'] or 0):.2f}",
        ]
        for i, v in enumerate(vals):
            p.drawString(col_x[i], y, v[:40])
        y -= 0.55 * cm

    p.showPage()
    p.save()
    return resp


# ================================================================
# CU25 – Historial de compras a proveedores
# ================================================================
def _build_order_mysql_compras(sort: str, direction: str) -> str:
    direction = (direction or "desc").lower()
    if direction not in ("asc", "desc"):
        direction = "desc"
    allowed = {
        "fecha": "c.fecha",
        "proveedor": "pr.nombre",
        "total": "c.total",
    }
    col = allowed.get((sort or "").lower(), "c.fecha")
    if direction == "asc":
        return f"CASE WHEN {col} IS NULL THEN 1 ELSE 0 END, {col} ASC"
    return f"{col} DESC"


def _fetch_historial_compras(
    q: str | None,
    d1: str | None,
    d2: str | None,
    order_sql: str,
    proveedor_id: str | None = None,
):
    """
    Devuelve una fila por compra.
    """
    where = ["1=1"]
    params: list = []

    if proveedor_id:
        where.append("c.proveedor_id = %s")
        params.append(proveedor_id)

    if q:
        where.append("""(
            pr.nombre    LIKE CONCAT('%%', %s, '%%')
         OR pr.telefono  LIKE CONCAT('%%', %s, '%%')
         OR pr.direccion LIKE CONCAT('%%', %s, '%%')
        )""")
        params.extend([q, q, q])

    if d1:
        where.append("DATE(c.fecha) >= %s")
        params.append(d1)
    if d2:
        where.append("DATE(c.fecha) <= %s")
        params.append(d2)

    where_sql = " AND ".join(where)

    sql = f"""
        SELECT
            c.id AS compra_id,
            DATE_FORMAT(c.fecha, '%%Y-%%m-%%d %%H:%%i') AS fecha,
            pr.id        AS proveedor_id,
            pr.nombre    AS proveedor,
            pr.telefono  AS telefono,
            pr.direccion AS direccion,
            c.total      AS total
        FROM compra c
        JOIN proveedor pr ON pr.id = c.proveedor_id
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT 500
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@login_required
@requiere_permiso("COMPRA_READ")
def historial_proveedores(request):
    q  = (request.GET.get("q") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None
    proveedor_id = (request.GET.get("proveedor_id") or "").strip() or None

    sort = request.GET.get("sort", "fecha")
    direction = request.GET.get("dir", "desc")
    order_sql = _build_order_mysql_compras(sort, direction)

    rows = _fetch_historial_compras(q, d1, d2, order_sql, proveedor_id=proveedor_id)

    total_compras = len(rows)
    total_monto   = sum(Decimal(r.get("total") or 0) for r in rows)

    def _next_dir(col: str) -> str:
        return "asc" if (direction == "desc" or sort != col) else "desc"

    return render(
        request,
        "accounts/historial_proveedores.html",
        {
            "rows": rows,
            "q": q or "",
            "d1": d1 or "",
            "d2": d2 or "",
            "proveedor_id": proveedor_id or "",
            "sort": sort,
            "dir": direction,
            "total_compras": total_compras,
            "total_monto": total_monto,
            "next_dir_fecha": _next_dir("fecha"),
            "next_dir_proveedor": _next_dir("proveedor"),
            "next_dir_total": _next_dir("total"),
        },
    )


@login_required
def historial_proveedores_csv(request):
    q  = (request.GET.get("q") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None
    proveedor_id = (request.GET.get("proveedor_id") or "").strip() or None

    rows = _fetch_historial_compras(
        q, d1, d2, _build_order_mysql_compras("fecha", "desc"),
        proveedor_id=proveedor_id,
    )

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="historial_compras_proveedores.csv"'
    w = csv.writer(resp)
    w.writerow(["Compra", "Fecha", "Proveedor", "Teléfono", "Dirección", "Total (Bs.)"])
    for r in rows:
        w.writerow([
            r.get("compra_id", ""),
            r.get("fecha", ""),
            r.get("proveedor", "") or "",
            r.get("telefono", "") or "",
            r.get("direccion", "") or "",
            f"{Decimal(r.get('total') or 0):.2f}",
        ])
    return resp


@login_required
def historial_proveedores_html(request):
    q  = (request.GET.get("q") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None
    proveedor_id = (request.GET.get("proveedor_id") or "").strip() or None

    rows = _fetch_historial_compras(
        q, d1, d2, _build_order_mysql_compras("fecha", "desc"),
        proveedor_id=proveedor_id,
    )

    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>Historial de compras a proveedores</title>",
        "<style>table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px}th{background:#f6f6f6;text-align:left}</style>",
        "</head><body>",
        "<h2>Historial de compras a proveedores</h2>",
        f"<p>Filtro q: {q or '-'} | Desde: {d1 or '-'} | Hasta: {d2 or '-'} | Proveedor: {proveedor_id or '-'}</p>",
        "<table><thead><tr>",
        "<th>#</th><th>Fecha</th><th>Proveedor</th><th>Teléfono</th><th>Dirección</th><th>Total (Bs.)</th>",
        "</tr></thead><tbody>",
    ]
    for r in rows:
        html.append(
            "<tr>"
            f"<td>{r.get('compra_id','')}</td>"
            f"<td>{r.get('fecha','')}</td>"
            f"<td>{(r.get('proveedor') or '')}</td>"
            f"<td>{(r.get('telefono') or '')}</td>"
            f"<td>{(r.get('direccion') or '')}</td>"
            f"<td>{Decimal(r.get('total') or 0):.2f}</td>"
            "</tr>"
        )
    html.append("</tbody></table></body></html>")

    return HttpResponse("".join(html), content_type="text/html; charset=utf-8")


@login_required
def historial_proveedores_pdf(request):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
    except Exception:
        return HttpResponse(
            "Exportación a PDF no disponible: instala 'reportlab' (pip install reportlab).",
            content_type="text/plain; charset=utf-8",
            status=200,
        )

    q  = (request.GET.get("q") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None
    proveedor_id = (request.GET.get("proveedor_id") or "").strip() or None

    rows = _fetch_historial_compras(
        q, d1, d2, _build_order_mysql_compras("fecha", "desc"),
        proveedor_id=proveedor_id,
    )

    resp = HttpResponse(content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="historial_compras_proveedores.pdf"'

    p = canvas.Canvas(resp, pagesize=landscape(A4))
    width, height = landscape(A4)
    x = 2 * cm
    y = height - 2 * cm

    p.setFont("Helvetica-Bold", 14)
    p.drawString(x, y, "Historial de compras a proveedores")
    y -= 0.8 * cm
    p.setFont("Helvetica", 10)
    p.drawString(x, y, f"Filtro q: {q or '-'}  |  Desde: {d1 or '-'}  |  Hasta: {d2 or '-'}  |  Proveedor: {proveedor_id or '-'}")
    y -= 1.0 * cm

    headers = ["#", "Fecha", "Proveedor", "Teléfono", "Dirección", "Total (Bs.)"]
    col_x = [x, x + 3.5*cm, x + 9.5*cm, x + 17*cm, x + 23*cm, x + 30*cm]

    p.setFont("Helvetica-Bold", 10)
    for i, h in enumerate(headers):
        p.drawString(col_x[i], y, h)
    y -= 0.6 * cm
    p.setFont("Helvetica", 10)

    for r in rows:
        if y < 1.5 * cm:
            p.showPage()
            p.setFont("Helvetica-Bold", 10)
            for i, h in enumerate(headers):
                p.drawString(col_x[i], height - 2 * cm, h)
            p.setFont("Helvetica", 10)
            y = height - 2.6 * cm

        vals = [
            str(r.get("compra_id","")),
            r.get("fecha",""),
            (r.get("proveedor") or ""),
            (r.get("telefono") or ""),
            (r.get("direccion") or ""),
            f"{Decimal(r.get('total') or 0):.2f}",
        ]
        for i, v in enumerate(vals):
            p.drawString(col_x[i], y, (v or "")[:60])
        y -= 0.55 * cm

    p.showPage()
    p.save()
    return resp


# ================================================================
# CU26 – Historial de entregas (repartidor / fechas / estado)
# ================================================================
def _build_order_mysql_entregas(sort: str, direction: str) -> str:
    direction = (direction or "desc").lower()
    if direction not in ("asc", "desc"):
        direction = "desc"

    allowed = {
        "fecha": "fecha",
        "repartidor": "repartidor",
        "cliente": "cliente",
        "estado": "estado",
    }
    col = allowed.get((sort or "").lower(), "fecha")
    if direction == "asc":
        return f"CASE WHEN {col} IS NULL THEN 1 ELSE 0 END, {col} ASC"
    return f"{col} DESC"


def _fetch_historial_entregas(
    q: str | None,
    estado: str | None,
    d1: str | None,
    d2: str | None,
    order_sql: str | None,
):
    """
    Devuelve una fila por envío/entrega con joins a cliente.
    Parche: la BD no tiene e.comentarios, por eso devolvemos '' AS comentario.
    """
    where = ["1=1"]
    params: list = []

    fecha_expr = "p.created_at"
    repartidor_expr = "COALESCE(NULLIF(TRIM(e.nombre_repartidor), ''), '—')"
    cliente_expr    = "COALESCE(NULLIF(TRIM(c.nombre), ''), u.email)"

    if q:
        where.append(f"""(
            {repartidor_expr} LIKE CONCAT('%%', %s, '%%')
         OR {cliente_expr}    LIKE CONCAT('%%', %s, '%%')
        )""")
        params.extend([q, q])

    if estado:
        where.append("e.estado = %s")
        params.append(estado)

    if d1:
        where.append(f"DATE({fecha_expr}) >= %s")
        params.append(d1)
    if d2:
        where.append(f"DATE({fecha_expr}) <= %s")
        params.append(d2)

    where_sql = " AND ".join(where)
    order_sql = order_sql or "fecha DESC"

    sql = f"""
        SELECT
            e.id                      AS envio_id,
            p.id                      AS pedido_id,
            DATE_FORMAT({fecha_expr}, '%%Y-%%m-%%d %%H:%%i') AS fecha,
            {repartidor_expr}         AS repartidor,
            {cliente_expr}            AS cliente,
            e.estado                  AS estado,
            p.metodo_envio            AS metodo_envio,
            p.direccion_entrega       AS direccion,
            p.total                   AS total,
            ''                        AS comentario
        FROM envio e
        JOIN pedido  p ON p.id = e.pedido_id
        LEFT JOIN cliente c ON c.id = p.cliente_id
        LEFT JOIN usuario u ON u.id = c.usuario_id
        WHERE {where_sql}
        ORDER BY {order_sql}
        LIMIT 1000
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        return [dict(zip(cols, row)) for row in cur.fetchall()]


@login_required
@requiere_permiso("PEDIDO_READ")  # o ENVIO_READ si lo tienes
def historial_entregas(request):
    q  = (request.GET.get("q") or "").strip() or None
    st = (request.GET.get("estado") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None

    sort = request.GET.get("sort", "fecha")
    direction = request.GET.get("dir", "desc")
    order_sql = _build_order_mysql_entregas(sort, direction)

    rows = _fetch_historial_entregas(q, st, d1, d2, order_sql)

    total_envios = len(rows)
    total_entregados = sum(1 for r in rows if (r.get("estado") or "").upper() == "ENTREGADO")

    def _next_dir(col: str) -> str:
        return "asc" if (direction == "desc" or sort != col) else "desc"

    return render(request, "accounts/historial_entregas.html", {
        "rows": rows,
        "q": q or "",
        "estado": st or "",
        "d1": d1 or "",
        "d2": d2 or "",
        "sort": sort, "dir": direction,
        "next_dir_fecha": _next_dir("fecha"),
        "next_dir_rep": _next_dir("repartidor"),
        "next_dir_cli": _next_dir("cliente"),
        "next_dir_est": _next_dir("estado"),
        "total_envios": total_envios,
        "total_entregados": total_entregados,
        "ESTADOS": ["PENDIENTE", "EN_CAMINO", "ENTREGADO", "CANCELADO"],
    })


# ----------------- Exportaciones CU26 -----------------
@login_required
@requiere_permiso("PEDIDO_READ")
def historial_entregas_csv(request):
    q  = (request.GET.get("q") or "").strip() or None
    st = (request.GET.get("estado") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None

    rows = _fetch_historial_entregas(q, st, d1, d2, _build_order_mysql_entregas("fecha", "desc"))

    resp = HttpResponse(content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename="historial_entregas.csv"'
    w = csv.writer(resp)
    w.writerow(["Envío", "Fecha", "Repartidor", "Cliente", "Pedido", "Estado", "Comentario"])
    for r in rows:
        w.writerow([
            r.get("envio_id", ""),
            r.get("fecha", "") or "",
            r.get("repartidor", "") or "",
            r.get("cliente", "") or "",
            r.get("pedido_id", "") or "",
            r.get("estado", "") or "",
            (r.get("comentario") or "").replace("\n", " ").strip()
        ])
    return resp


@login_required
@requiere_permiso("PEDIDO_READ")
def historial_entregas_html(request):
    q  = (request.GET.get("q") or "").strip() or None
    st = (request.GET.get("estado") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None

    rows = _fetch_historial_entregas(q, st, d1, d2, _build_order_mysql_entregas("fecha", "desc"))

    html = [
        "<!doctype html><html><head><meta charset='utf-8'><title>Historial de entregas</title>",
        "<style>table{border-collapse:collapse;width:100%}th,td{border:1px solid #ccc;padding:6px}th{background:#f6f6f6;text-align:left}</style>",
        "</head><body>",
        "<h2>Historial de entregas</h2>",
        f"<p>Filtro: {q or '-'} | Estado: {st or '-'} | Desde: {d1 or '-'} | Hasta: {d2 or '-'}</p>",
        "<table><thead><tr>",
        "<th>#</th><th>Fecha</th><th>Repartidor</th><th>Cliente</th><th>Pedido</th><th>Estado</th><th>Comentario</th>",
        "</tr></thead><tbody>",
    ]
    for r in rows:
        html.append(
            "<tr>"
            f"<td>{r.get('envio_id','')}</td>"
            f"<td>{r.get('fecha','')}</td>"
            f"<td>{(r.get('repartidor') or '')}</td>"
            f"<td>{(r.get('cliente') or '')}</td>"
            f"<td>{r.get('pedido_id','')}</td>"
            f"<td>{(r.get('estado') or '')}</td>"
            f"<td>{(r.get('comentario') or '').replace('<','&lt;').replace('>','&gt;')}</td>"
            "</tr>"
        )
    html.append("</tbody></table></body></html>")
    return HttpResponse("".join(html), content_type="text/html; charset=utf-8")


@login_required
@requiere_permiso("PEDIDO_READ")
def historial_entregas_pdf(request):
    try:
        from reportlab.lib.pagesizes import A4, landscape
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
    except Exception:
        return HttpResponse(
            "Exportación a PDF no disponible: instala 'reportlab' (pip install reportlab).",
            content_type="text/plain; charset=utf-8",
            status=200,
        )

    q  = (request.GET.get("q") or "").strip() or None
    st = (request.GET.get("estado") or "").strip() or None
    d1 = (request.GET.get("d1") or "").strip() or None
    d2 = (request.GET.get("d2") or "").strip() or None

    rows = _fetch_historial_entregas(q, st, d1, d2, _build_order_mysql_entregas("fecha", "desc"))

    resp = HttpResponse(content_type="application/pdf")
    resp["Content-Disposition"] = 'attachment; filename="historial_entregas.pdf"'

    p = canvas.Canvas(resp, pagesize=landscape(A4))
    width, height = landscape(A4)
    x = 2 * cm
    y = height - 2 * cm

    p.setFont("Helvetica-Bold", 14)
    p.drawString(x, y, "Historial de entregas")
    y -= 0.8 * cm
    p.setFont("Helvetica", 10)
    p.drawString(x, y, f"Filtro: {q or '-'} | Estado: {st or '-'} | Desde: {d1 or '-'} | Hasta: {d2 or '-'}")
    y -= 1.0 * cm

    headers = ["#", "Fecha", "Repartidor", "Cliente", "Pedido", "Estado", "Comentario"]
    col_x = [x, x + 3.2*cm, x + 9.2*cm, x + 16.2*cm, x + 23*cm, x + 27*cm, x + 31*cm]

    p.setFont("Helvetica-Bold", 10)
    for i, h in enumerate(headers):
        p.drawString(col_x[i], y, h)
    y -= 0.6 * cm
    p.setFont("Helvetica", 10)

    for r in rows:
        if y < 1.5 * cm:
            p.showPage()
            p.setFont("Helvetica-Bold", 10)
            for i, h in enumerate(headers):
                p.drawString(col_x[i], height - 2 * cm, h)
            p.setFont("Helvetica", 10)
            y = height - 2.6 * cm

        vals = [
            str(r.get("envio_id", "")),
            r.get("fecha", "") or "",
            (r.get("repartidor") or ""),
            (r.get("cliente") or ""),
            str(r.get("pedido_id", "")),
            (r.get("estado") or ""),
            (r.get("comentario") or "")[:80].replace("\n", " "),
        ]
        for i, v in enumerate(vals):
            p.drawString(col_x[i], y, v[:60])
        y -= 0.55 * cm

    p.showPage()
    p.save()
    return resp


# ================================================================
# CU27 – Generar reportes de ventas (dispatcher ?export=)
# ================================================================
# --- CU27 helpers (REEMPLAZA ESTAS DOS FUNCIONES) ---

def _ventas_build_where(q: str | None, d1: str | None, d2: str | None) -> tuple[str, list]:
    where = ["1=1"]
    params: list = []

    # usa fecha_emision de la factura; si no hubiera, cae a la del pedido
    fecha_expr   = "COALESCE(f.fecha, p.created_at)"
    cliente_expr = "COALESCE(NULLIF(TRIM(c.nombre), ''), u.email)"
    sabor_expr   = "COALESCE(NULLIF(TRIM(s.nombre), ''), '—')"

    if q:
        where.append(f"({cliente_expr} LIKE CONCAT('%%', %s, '%%') OR {sabor_expr} LIKE CONCAT('%%', %s, '%%'))")
        params.extend([q, q])

    if d1:
        where.append(f"DATE({fecha_expr}) >= %s")
        params.append(d1)
    if d2:
        where.append(f"DATE({fecha_expr}) <= %s")
        params.append(d2)

    return " AND ".join(where), params


from django.db import connection

def _fetch_ventas_agregado(group: str, q: str | None, d1: str | None, d2: str | None):
    """
    Agrupa ventas por día/cliente/sabor/producto usando tu esquema real:
      - fecha de la factura: factura.fecha
      - sabores vía detalle_pedido -> sabor
      - producto vía detalle_pedido -> producto
    Retorna (data, total_general, ventas_total)
    """
    # ✨ Campos legibles
    fecha_factura   = "f.fecha"  # <- existe en tu tabla factura
    cliente_expr    = "COALESCE(NULLIF(TRIM(c.nombre), ''), u.email)"
    sabor_expr      = "COALESCE(NULLIF(TRIM(s.nombre), ''), '—')"
    producto_expr   = "COALESCE(NULLIF(TRIM(pr.nombre), ''), '—')"

    # Normalizamos parámetro
    g = (group or "dia").lower()

    if g == "cliente":
        etiqueta = cliente_expr
        order_by = "total DESC"
    elif g == "sabor":
        etiqueta = sabor_expr
        order_by = "total DESC"
    elif g == "producto":
        etiqueta = producto_expr
        order_by = "total DESC"
    else:
        # por día (desde fecha de la factura)
        etiqueta = f"DATE_FORMAT({fecha_factura}, '%%Y-%%m-%%d')"
        order_by = "etiqueta ASC"

    # 🔎 Filtros (ajusta si tu helper se llama distinto)
    where_parts = ["1=1"]
    params = []

    # rango de fechas sobre la fecha de la factura
    if d1:
        where_parts.append(f"{fecha_factura} >= %s")
        params.append(d1)
    if d2:
        where_parts.append(f"{fecha_factura} < DATE_ADD(%s, INTERVAL 1 DAY)")
        params.append(d2)

    # búsqueda libre (cliente/sabor/producto)
    if q:
        where_parts.append(f"""(
            {cliente_expr} LIKE %s OR
            {sabor_expr}   LIKE %s OR
            {producto_expr} LIKE %s
        )""")
        like = f"%{q}%"
        params += [like, like, like]

    where = " AND ".join(where_parts)

    # 🧩 Joins usando tu modelo de datos
    sql = f"""
        SELECT
            {etiqueta} AS etiqueta,
            COUNT(DISTINCT p.id) AS ventas,
            SUM(p.total) AS total
        FROM factura f
        JOIN pedido   p  ON p.id = f.pedido_id
        LEFT JOIN cliente  c  ON c.id = p.cliente_id
        LEFT JOIN usuario  u  ON u.id = c.usuario_id

        -- Detalle para llegar a sabor y producto
        LEFT JOIN detalle_pedido dp ON dp.pedido_id = p.id
        LEFT JOIN sabor          s  ON s.id = dp.sabor_id
        LEFT JOIN producto       pr ON pr.id = dp.producto_id

        WHERE {where}
        GROUP BY etiqueta
        ORDER BY {order_by}
        LIMIT 2000
    """

    with connection.cursor() as cur:
        cur.execute(sql, params)
        cols = [c[0] for c in cur.description]
        data = [dict(zip(cols, row)) for row in cur.fetchall()]

    total_general = sum((r["total"] or 0) for r in data)
    ventas_total  = sum((r["ventas"] or 0) for r in data)
    return data, total_general, ventas_total


# Vistas internas de CU27
def _ventas_html_ctx(request):
    group = request.GET.get("group", "dia")
    q     = (request.GET.get("q") or "").strip() or None
    d1    = request.GET.get("d1") or None
    d2    = request.GET.get("d2") or None
    data, total_general, ventas_total = _fetch_ventas_agregado(group, q, d1, d2)
    return {
        "hoy": now(),
        "rows": data,
        "group": group,
        "q": q or "",
        "d1": d1 or "",
        "d2": d2 or "",
        "total_general": total_general,
        "ventas_total": ventas_total,
    }


def ventas_reportes(request):
    ctx = _ventas_html_ctx(request)
    return render(request, "accounts/ventas_reportes.html", ctx)


def ventas_reportes_html(request):
    ctx = _ventas_html_ctx(request)
    return render(request, "accounts/ventas_reportes_print.html", ctx)


def ventas_reportes_csv(request):
    group = request.GET.get("group", "dia")
    q     = (request.GET.get("q") or "").strip() or None
    d1    = request.GET.get("d1") or None
    d2    = request.GET.get("d2") or None

    data, total_general, ventas_total = _fetch_ventas_agregado(group, q, d1, d2)

    lines = ["etiqueta,ventas,total"]
    for r in data:
        etiqueta = (r["etiqueta"] or "").replace(",", " ")
        lines.append(f"{etiqueta},{r['ventas']},{r['total'] or 0}")
    lines.append(f"TOTAL,{ventas_total},{total_general}")

    resp = HttpResponse("\n".join(lines), content_type="text/csv; charset=utf-8")
    resp["Content-Disposition"] = 'attachment; filename=\"ventas_reportes.csv\"'
    return resp


def ventas_reportes_pdf(request):
    # Si luego usas un generador de PDF, conviertes el HTML de impresión.
    resp = ventas_reportes_html(request)
    resp["Content-Disposition"] = 'attachment; filename=\"ventas_reportes.html\"'
    return resp


# Dispatcher pedido por urls.py
@login_required
@requiere_permiso("PEDIDO_READ")
def reporte_ventas(request):
    """
    /reportes/ventas/?group=dia|cliente|producto|sabor&d1=YYYY-MM-DD&d2=YYYY-MM-DD&q=...
    &export=csv|html|pdf
    """
    export = (request.GET.get("export") or "").lower()
    if export == "csv":
        return ventas_reportes_csv(request)
    if export == "html":
        return ventas_reportes_html(request)
    if export == "pdf":
        return ventas_reportes_pdf(request)
    return ventas_reportes(request)
