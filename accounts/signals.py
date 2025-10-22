# accounts/signals.py
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from django.contrib.auth import get_user_model
from django.db import connection, transaction
from .utils import log_event

User = get_user_model()

# -------------------------------------------------------------------
# Helpers DB
# -------------------------------------------------------------------
def _exec(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])

def _fetchone(sql, params=None):
    with connection.cursor() as cur:
        cur.execute(sql, params or [])
        return cur.fetchone()

# -------------------------------------------------------------------
# Bootstrap de permisos/roles mínimos
# -------------------------------------------------------------------
def ensure_perm_exists(codigo: str, descripcion: str = None):
    _exec("""
        INSERT INTO permiso (codigo, descripcion)
        SELECT %s, %s
        WHERE NOT EXISTS (SELECT 1 FROM permiso WHERE codigo=%s)
    """, [codigo, descripcion or codigo, codigo])

def ensure_role_exists(nombre: str):
    _exec("""
        INSERT INTO rol (nombre)
        SELECT %s
        WHERE NOT EXISTS (SELECT 1 FROM rol WHERE nombre=%s)
    """, [nombre, nombre])

def ensure_role_has_perm(rol: str, permiso: str):
    row = _fetchone("SELECT id FROM rol WHERE nombre=%s", [rol])
    if not row:
        return
    rol_id = row[0]
    row = _fetchone("SELECT id FROM permiso WHERE codigo=%s", [permiso])
    if not row:
        return
    permiso_id = row[0]
    _exec("""
        INSERT INTO rol_permiso (rol_id, permiso_id)
        SELECT %s, %s
        WHERE NOT EXISTS(
          SELECT 1 FROM rol_permiso WHERE rol_id=%s AND permiso_id=%s
        )
    """, [rol_id, permiso_id, rol_id, permiso_id])

def bootstrap_roles_perms():
    ensure_perm_exists("PEDIDO_READ", "Puede ver pedidos")
    ensure_role_exists("CLIENTE")
    ensure_role_has_perm("CLIENTE", "PEDIDO_READ")

# -------------------------------------------------------------------
# Sincronización Django User -> tabla accounts.usuario
# -------------------------------------------------------------------
def ensure_usuario_row(email: str, nombre: str = "", password_hash: str = "") -> int | None:
    """
    Crea (o actualiza) la fila en `usuario` para el email dado.
    Escribe también `hash_password` para cumplir NOT NULL.
    """
    if not email:
        return None

    # ¿existe ya?
    row = _fetchone("SELECT id, hash_password FROM usuario WHERE LOWER(email)=LOWER(%s) LIMIT 1", [email])
    if row:
        uid, db_hash = row[0], row[1]
        # Si tenemos un hash nuevo de Django y cambió, lo sincronizamos.
        if password_hash and password_hash != (db_hash or ""):
            _exec("""
                UPDATE usuario
                   SET hash_password = %s,
                       nombre = CASE WHEN %s <> '' THEN %s ELSE nombre END
                 WHERE id = %s
            """, [password_hash, nombre or "", nombre or "", uid])
        return uid

    # No existe: insertamos incluyendo hash_password
    _exec("""
        INSERT INTO usuario (nombre, email, activo, hash_password)
        VALUES (%s, %s, 1, %s)
    """, [nombre or email, email, password_hash or ""])

    row = _fetchone("SELECT id FROM usuario WHERE LOWER(email)=LOWER(%s) LIMIT 1", [email])
    return row[0] if row else None

def ensure_usuario_has_role(usuario_id: int, rol_nombre: str):
    row = _fetchone("SELECT id FROM rol WHERE nombre=%s", [rol_nombre])
    if not row:
        return
    rol_id = row[0]
    _exec("""
        INSERT INTO usuario_rol (usuario_id, rol_id)
        SELECT %s, %s
        WHERE NOT EXISTS(
          SELECT 1 FROM usuario_rol WHERE usuario_id=%s AND rol_id=%s
        )
    """, [usuario_id, rol_id, usuario_id, rol_id])

def sync_app_usuario_from_auth(user: User):
    """
    A partir del auth.User de Django, asegura fila en `usuario`,
    sincroniza el hash y asigna rol CLIENTE con PEDIDO_READ.
    """
    if not user or not getattr(user, "email", ""):
        return
    bootstrap_roles_perms()

    nombre = (user.get_full_name() or user.first_name or user.username or "").strip()
    # Django guarda el hash en user.password (pbkdf2_sha256$....)
    password_hash = user.password or ""

    with transaction.atomic():
        uid = ensure_usuario_row(user.email, nombre, password_hash=password_hash)
        if uid:
            ensure_usuario_has_role(uid, "CLIENTE")

# -------------------------------------------------------------------
# Receivers (bitácora + auto-sync)
# -------------------------------------------------------------------
@receiver(user_logged_in)
def on_login(sender, request, user, **kwargs):
    # Bitácora
    log_event(request, "Auth", getattr(user, "id", 0), "Login")
    # Sincronización
    try:
        sync_app_usuario_from_auth(user)
    except Exception:
        # Evita que un fallo de sync corte el login. Loguea si quieres.
        pass

@receiver(user_logged_out)
def on_logout(sender, request, user, **kwargs):
    log_event(request, "Auth", getattr(user, "id", 0), "Logout")
