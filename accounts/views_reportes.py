# accounts/views_reportes.py
from __future__ import annotations
from datetime import datetime
from decimal import Decimal
import csv

from django.http import HttpResponse
from django.shortcuts import render
from django.db import connection
from django.contrib.auth.decorators import login_required

# Usa tu decorador de permisos por código
from .permissions import requiere_permiso

# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _build_order_mysql(sort: str, direction: str) -> str:
    """
    Devuelve un ORDER BY compatible con MySQL y con 'NULLS LAST' simulado cuando es ASC.
    sort: 'cliente' | 'creado' | 'total' | 'estado'
    direction: 'asc' | 'desc'
    """
    direction = (direction or "desc").lower()
    if direction not in ("asc", "desc"):
        direction = "desc"

    allowed = {
        "cliente": "cliente",      # alias del SELECT
        "creado":  "p.created_at", # campo real (no seleccionado, pero válido en ORDER BY)
        "total":   "p.total",
        "estado":  "p.estado",
    }
    col = allowed.get((sort or "").lower(), "p.created_at")

    if direction == "asc":
        # Simula NULLS LAST en ASC
        return f"CASE WHEN {col} IS NULL THEN 1 ELSE 0 END, {col} ASC"
    else:
        return f"{col} DESC"  # en DESC los NULLs ya quedan últimos en MySQL


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


def _fetch_historial(q: str | None, d1: str | None, d2: str | None, order_sql: str):
    """
    Trae los pedidos confirmados con totales y pagado agregado.
    Se filtra por nombre/email (LIKE) y rango de fechas en created_at.
    El ORDER BY se pasa como cadena previamente *whitelisteada* (order_sql).
    """
    where = ["p.estado = 'CONFIRMADO'"]
    params: list = []

    if q:
        # evita poner % crudos en el SQL; usa CONCAT
        where.append("(u.email LIKE CONCAT('%%', %s, '%%') OR u.nombre LIKE CONCAT('%%', %s, '%%'))")
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

# -------------------------------------------------------------------
# Vistas
# -------------------------------------------------------------------
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

    # Totales para la cabecera (opcional)
    total_clientes = len(rows)
    total_pedidos = sum(r.get("pedido_id") is not None for r in rows)  # conteo de filas (una por pedido)
    total_monto = sum(Decimal(r["total"] or 0) for r in rows)

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
            "total_clientes": total_clientes,
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

    # Orden por defecto para export: último primero
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
            "Exportación a PDF no disponible: instala 'reportlab' (pip install reportlab). "
            "Puedes usar la exportación HTML/CSV.",
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
