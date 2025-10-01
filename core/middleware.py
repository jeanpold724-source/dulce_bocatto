# core/middleware.py
from accounts.utils import log_event  # usamos tu helper

class AuditWriteMiddleware:
    """
    Registra en bitácora cualquier request de escritura (POST/PUT/PATCH/DELETE).
    No bloquea el flujo si algo falla.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            if getattr(request, "user", None) and request.user.is_authenticated:
                if request.method in ("POST", "PUT", "PATCH", "DELETE"):
                    # Guardamos ruta y método
                    log_event(request, "HTTP", 0, f"{request.method} {request.path}")
        except Exception:
            # Nunca botar el request por problemas de logging
            pass
        return response
