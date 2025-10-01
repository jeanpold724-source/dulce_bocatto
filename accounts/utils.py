# accounts/utils.py
from django.utils import timezone

def ip_from_request(request):
    return request.META.get("HTTP_X_FORWARDED_FOR", request.META.get("REMOTE_ADDR", ""))

def log_event(request, entidad: str, entidad_id: int | None, accion: str):
    # Import local para evitar import circular con signals/apps/models_db
    from .models_db import Bitacora, Usuario

    try:
        email = (getattr(request.user, "email", "") or "").strip().lower()
        u = Usuario.objects.filter(email=email).first()
        Bitacora.objects.create(
            usuario=u,                 # si no permite NULL, usa un usuario “sistema”
            entidad=entidad,
            entidad_id=entidad_id or 0,
            accion=accion,
            ip=ip_from_request(request),
            fecha=timezone.now(),
        )
    except Exception:
        # No bloquear el flujo si la bitácora falla
        pass
