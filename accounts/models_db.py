# accounts/models_db.py
from django.db import models


# ============================
# Tablas del admin de Django (solo lectura)
# ============================

class AccountsUser(models.Model):
    id = models.BigAutoField(primary_key=True)
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()
    email = models.CharField(unique=True, max_length=254)
    phone = models.CharField(max_length=40, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'accounts_user'

    def __str__(self):
        return self.username


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'

    def __str__(self):
        return self.name


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)

    def __str__(self):
        return self.codename


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AccountsUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AccountsUser, models.DO_NOTHING)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'accounts_user_groups'
        unique_together = (('user', 'group'),)


class AccountsUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AccountsUser, models.DO_NOTHING)
    permission = models.ForeignKey(AuthPermission, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'accounts_user_user_permissions'
        unique_together = (('user', 'permission'),)


class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING, blank=True, null=True)
    user = models.ForeignKey(AccountsUser, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'django_admin_log'


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'


class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'


# ============================
# Seguridad propia (usuarios/roles/permisos)
# ============================

class Usuario(models.Model):
    nombre = models.CharField(max_length=120)
    email = models.CharField(unique=True, max_length=160)
    hash_password = models.CharField(max_length=200)
    telefono = models.CharField(max_length=40, blank=True, null=True)
    activo = models.IntegerField()
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'usuario'

    def __str__(self):
        return f"{self.nombre} <{self.email}>"


class Rol(models.Model):
    nombre = models.CharField(unique=True, max_length=80)

    class Meta:
        managed = False
        db_table = 'rol'

    def __str__(self):
        return self.nombre


class Permiso(models.Model):
    codigo = models.CharField(unique=True, max_length=80)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'permiso'

    def __str__(self):
        return self.codigo


class UsuarioRol(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario = models.ForeignKey('Usuario', on_delete=models.PROTECT, db_column='usuario_id')
    rol = models.ForeignKey('Rol', on_delete=models.PROTECT, db_column='rol_id')

    class Meta:
        managed = False
        db_table = 'usuario_rol'
        unique_together = (('usuario', 'rol'),)

    def __str__(self):
        return f"{self.usuario} → {self.rol}"


class RolPermiso(models.Model):
    id = models.BigAutoField(primary_key=True)
    rol = models.ForeignKey('Rol', on_delete=models.PROTECT, db_column='rol_id')
    permiso = models.ForeignKey('Permiso', on_delete=models.PROTECT, db_column='permiso_id')

    class Meta:
        managed = False
        db_table = 'rol_permiso'
        unique_together = (('rol', 'permiso'),)

    def __str__(self):
        return f"{self.rol} → {self.permiso}"


class Bitacora(models.Model):
    usuario = models.ForeignKey('Usuario', models.DO_NOTHING)
    entidad = models.CharField(max_length=60)
    entidad_id = models.IntegerField()
    accion = models.CharField(max_length=50)
    ip = models.CharField(max_length=64, blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'bitacora'

    def __str__(self):
        return f"[{self.fecha}] {self.usuario} {self.accion} {self.entidad}({self.entidad_id})"


# ============================
# Clientes & Ventas
# ============================

class Cliente(models.Model):
    usuario = models.OneToOneField('Usuario', models.DO_NOTHING)
    nombre = models.CharField(max_length=120)
    telefono = models.CharField(max_length=40, blank=True, null=True)
    direccion = models.CharField(max_length=200)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cliente'

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    nombre = models.CharField(unique=True, max_length=120)
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    activo = models.IntegerField()
    descripcion = models.CharField(max_length=300, blank=True, null=True)
    imagen_url = models.CharField(max_length=300, blank=True, null=True)
    creado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'producto'

    def __str__(self):
        return self.nombre


class Sabor(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    activo = models.IntegerField()
    imagen = models.CharField(max_length=200, blank=True, null=True, db_column='imagen')

    class Meta:
        managed = False
        db_table = 'sabor'

    def __str__(self):
        return self.nombre


class ProductoSabor(models.Model):
    id = models.BigAutoField(primary_key=True)
    producto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='producto_id')
    sabor = models.ForeignKey(Sabor, models.DO_NOTHING, db_column='sabor_id')

    class Meta:
        managed = False
        db_table = 'producto_sabor'
        unique_together = (('producto', 'sabor'),)

    def __str__(self):
        return f"{self.producto} - {self.sabor}"


class Descuento(models.Model):
    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=10)  # 'FIJO' | 'PORCENTAJE'
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    activo = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'descuento'

    def __str__(self):
        return f"{self.nombre} ({self.tipo})"
    

# (arriba del modelo Pedido)
from django.db import models

class EstadoPedido(models.TextChoices):
    PENDIENTE      = 'PENDIENTE', 'Pendiente'
    CONFIRMADO     = 'CONFIRMADO', 'Confirmado'
    EN_PRODUCCION  = 'EN_PRODUCCION', 'En producción'
    LISTO_ENTREGA  = 'LISTO_ENTREGA', 'Listo para entrega'
    ENTREGADO      = 'ENTREGADO', 'Entregado'
    CANCELADO      = 'CANCELADO', 'Cancelado'



# Reemplaza tu modelo Pedido actual por este (o ajusta solo el field estado)
class Pedido(models.Model):
    id = models.AutoField(primary_key=True)
    cliente = models.ForeignKey(Cliente, models.DO_NOTHING, db_column='cliente_id')

    # ✅ sube max_length y agrega choices
    estado = models.CharField(
        max_length=20,                      # antes tenías 10
        choices=EstadoPedido.choices,       # valida contra los 6 estados
        blank=True,
        null=True,                          # déjalo True si en tu BD hay nulls
        default=EstadoPedido.PENDIENTE,     # opcional pero recomendado
    )

    metodo_envio = models.CharField(max_length=20)  # RETIRO/DELIVERY
    costo_envio = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    direccion_entrega = models.CharField(max_length=200, blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    observaciones = models.CharField(max_length=300, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    fecha_entrega_programada = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pedido'

    def __str__(self):
        return f"Pedido #{self.id} ({self.estado})"


class PedidoDescuento(models.Model):
    id = models.BigAutoField(primary_key=True)
    pedido = models.ForeignKey(Pedido, models.DO_NOTHING, db_column='pedido_id')
    descuento = models.ForeignKey(Descuento, models.DO_NOTHING, db_column='descuento_id')
    monto_aplicado = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pedido_descuento'
        unique_together = (('pedido', 'descuento'),)


class Envio(models.Model):
    pedido = models.OneToOneField(Pedido, models.DO_NOTHING)
    estado = models.CharField(max_length=9, blank=True, null=True)  # PENDIENTE/ENTREGADO
    nombre_repartidor = models.CharField(max_length=120, blank=True, null=True)
    telefono_repartidor = models.CharField(max_length=40, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'envio'


class Factura(models.Model):
    pedido = models.OneToOneField(Pedido, models.DO_NOTHING)
    nro = models.CharField(unique=True, max_length=60)
    fecha = models.DateTimeField(blank=True, null=True)
    nit_cliente = models.CharField(max_length=60)
    razon_social = models.CharField(max_length=200)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'factura'


class Calificacion(models.Model):
    pedido = models.OneToOneField(Pedido, models.DO_NOTHING)
    puntaje = models.IntegerField()
    comentario = models.CharField(max_length=300, blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'calificacion'


# ============================
# Producción & Almacén
# ============================

class Insumo(models.Model):
    UNIDADES = (("kg", "kg"), ("g", "g"), ("lt", "lt"), ("ml", "ml"), ("und", "und"), ("bote", "bote"))

    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=120, unique=True)
    unidad_medida = models.CharField(max_length=10, choices=UNIDADES)
    cantidad_disponible = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    fecha_actualizacion = models.DateTimeField(auto_now=True, editable=False)

    class Meta:
        db_table = 'insumo'
        managed = False
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Kardex(models.Model):
    insumo = models.ForeignKey(Insumo, models.DO_NOTHING)
    fecha = models.DateTimeField(blank=True, null=True)
    tipo = models.CharField(max_length=7)    # ENTRADA/SALIDA/AJUSTE
    motivo = models.CharField(max_length=7)  # COMPRA/CONSUMO/AJUSTE
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    observacion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'kardex'




# ============================
# Compras & Proveedores
# ============================

class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=40, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'proveedor'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Compra(models.Model):
    id = models.AutoField(primary_key=True)
    proveedor = models.ForeignKey(Proveedor, models.DO_NOTHING, db_column='proveedor_id')
    fecha = models.DateTimeField(blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    # Flags CU14:
    recepcionada = models.BooleanField(default=False)
    fecha_recepcion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'compra'

    def __str__(self):
        return f"Compra #{self.id} - {self.proveedor}"


class CompraDetalle(models.Model):
    id = models.BigAutoField(primary_key=True)
    compra = models.ForeignKey(Compra, models.DO_NOTHING, db_column='compra_id')
    insumo = models.ForeignKey(Insumo, models.DO_NOTHING, db_column='insumo_id')
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    # No declarar 'subtotal' (columna generada en MySQL)

    class Meta:
        managed = False
        db_table = 'compra_detalle'
        unique_together = (('compra', 'insumo'),)

    def __str__(self):
        return f"{self.compra} · {self.insumo} · {self.cantidad}"



# accounts/models_db.py
from decimal import Decimal
from django.db import models

class Pago(models.Model):
    id = models.AutoField(primary_key=True)
    pedido = models.ForeignKey('Pedido', db_column='pedido_id', on_delete=models.DO_NOTHING)
    metodo = models.CharField(max_length=20)  # ENUM('EFECTIVO','QR','TRANSFERENCIA')
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    referencia = models.CharField(max_length=120, null=True, blank=True)
    registrado_por = models.ForeignKey('Usuario', db_column='registrado_por_id',
                                       on_delete=models.DO_NOTHING)
    created_at = models.DateTimeField()

    class Meta:
        managed = False         # usamos la tabla existente
        db_table = 'pago'

    def __str__(self):
        return f"Pago #{self.id} – {self.metodo} – {self.monto}"




# --- Detalle de Pedido ---
class DetallePedido(models.Model):
    id = models.BigAutoField(primary_key=True)  # <— necesario
    pedido   = models.ForeignKey(Pedido,   models.DO_NOTHING, db_column='pedido_id')
    producto = models.ForeignKey(Producto, models.DO_NOTHING, db_column='producto_id')
    sabor    = models.ForeignKey(Sabor,    models.DO_NOTHING, db_column='sabor_id')
    cantidad = models.IntegerField()
    precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    sub_total = models.DecimalField(max_digits=12, decimal_places=2)  # columna generada en MySQL

    class Meta:
        managed = False
        db_table = 'detalle_pedido'
        unique_together = (('pedido','producto','sabor'),)  # mantiene la regla de unicidad
