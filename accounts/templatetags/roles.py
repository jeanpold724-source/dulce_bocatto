from django import template

register = template.Library()

@register.filter
def has_rol(user, nombre_rol: str) -> bool:
    """
    Devuelve True si el usuario tiene un rol con ese nombre.
    Usa la relación UsuarioRol (related_name por defecto: usuario_rol_set).
    """
    if not getattr(user, "is_authenticated", False):
        return False
    try:
        return user.usuario_rol_set.filter(rol__nombre=nombre_rol).exists()
    except Exception:
        return False
