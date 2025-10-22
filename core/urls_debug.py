from django.http import HttpResponse
from django.urls import URLPattern, URLResolver, get_resolver

def urls_debug_view(request):
    resolver = get_resolver()
    rows = []

    def walk(prefix, patterns):
        for p in patterns:
            if isinstance(p, URLPattern):
                rows.append((str(prefix) + str(p.pattern), p.name or "—"))
            elif isinstance(p, URLResolver):
                walk(str(prefix) + str(p.pattern), p.url_patterns)

    walk("", resolver.url_patterns)
    rows.sort()

    html = "<h2>Rutas del proyecto</h2><ul>"
    html += "".join(f"<li><code>{pat}</code> — <b>{name}</b></li>" for pat, name in rows)
    html += "</ul>"
    return HttpResponse(html)
