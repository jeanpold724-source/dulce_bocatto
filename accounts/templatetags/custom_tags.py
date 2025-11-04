from django import template

register = template.Library()

@register.filter
def has_rol(user, rol_nombre):
    """Devuelve True si el usuario tiene el rol especificado."""
    return user.is_authenticated and user.usuario_rol_set.filter(rol__nombre=rol_nombre).exists()
