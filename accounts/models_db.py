# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models



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


class AccountsUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AccountsUser, models.DO_NOTHING)
    group = models.ForeignKey('AuthGroup', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'accounts_user_groups'
        unique_together = (('user', 'group'),)


class AccountsUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user = models.ForeignKey(AccountsUser, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'accounts_user_user_permissions'
        unique_together = (('user', 'permission'),)


class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'


class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group = models.ForeignKey(AuthGroup, models.DO_NOTHING)
    permission = models.ForeignKey('AuthPermission', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group', 'permission'),)


class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type = models.ForeignKey('DjangoContentType', models.DO_NOTHING)
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type', 'codename'),)


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


class Calificacion(models.Model):
    pedido = models.OneToOneField('Pedido', models.DO_NOTHING)
    puntaje = models.IntegerField()
    comentario = models.CharField(max_length=300, blank=True, null=True)
    fecha = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'calificacion'


class Cliente(models.Model):
    usuario = models.OneToOneField('Usuario', models.DO_NOTHING)
    nombre = models.CharField(max_length=120)
    telefono = models.CharField(max_length=40, blank=True, null=True)
    direccion = models.CharField(max_length=200)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'cliente'


# accounts/models_db.py

class Compra(models.Model):
    id = models.AutoField(primary_key=True)
    proveedor = models.ForeignKey("Proveedor", models.DO_NOTHING, db_column="proveedor_id")
    fecha = models.DateTimeField(blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    # 👇 agrega estos dos campos para que coincidan con tu tabla
    recepcionada = models.BooleanField(default=False)          # TINYINT(1) en MySQL
    fecha_recepcion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = "compra"



class CompraDetalle(models.Model):
    id = models.BigAutoField(primary_key=True)
    compra = models.ForeignKey(Compra, models.DO_NOTHING, db_column="compra_id")
    insumo = models.ForeignKey("Insumo", models.DO_NOTHING, db_column="insumo_id")  # <- comillas
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    costo_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    # NO declares 'subtotal'

    class Meta:
        managed = False
        db_table = "compra_detalle"
        unique_together = (("compra", "insumo"),)





class Descuento(models.Model):
    nombre = models.CharField(max_length=120)
    tipo = models.CharField(max_length=10)
    valor = models.DecimalField(max_digits=12, decimal_places=2)
    activo = models.IntegerField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'descuento'


#class DetallePedido(models.Model):
#    pk = models.CompositePrimaryKey('pedido_id', 'producto_id', 'sabor_id')
 #   pedido = models.ForeignKey('Pedido', models.DO_NOTHING)
  #  producto = models.ForeignKey('ProductoSabor', models.DO_NOTHING)
   # sabor = models.ForeignKey('ProductoSabor', models.DO_NOTHING, to_field='sabor_id', related_name='detallepedido_sabor_set')
    #cantidad = models.IntegerField()
    #precio_unitario = models.DecimalField(max_digits=12, decimal_places=2)
    #sub_total = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    #class Meta:
     #   managed = False
      #  db_table = 'detalle_pedido'


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


class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)


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


class Envio(models.Model):
    pedido = models.OneToOneField('Pedido', models.DO_NOTHING)
    estado = models.CharField(max_length=9, blank=True, null=True)
    nombre_repartidor = models.CharField(max_length=120, blank=True, null=True)
    telefono_repartidor = models.CharField(max_length=40, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'envio'


class Factura(models.Model):
    pedido = models.OneToOneField('Pedido', models.DO_NOTHING)
    nro = models.CharField(unique=True, max_length=60)
    fecha = models.DateTimeField(blank=True, null=True)
    nit_cliente = models.CharField(max_length=60)
    razon_social = models.CharField(max_length=200)
    total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'factura'



class Insumo(models.Model):
    UNIDADES = (
        ("kg","kg"),("g","g"),("lt","lt"),("ml","ml"),("und","und"),("bote","bote"),
    )

    id = models.AutoField(primary_key=True)
    nombre = models.CharField(max_length=120, unique=True)
    unidad_medida = models.CharField(max_length=10, choices=UNIDADES)
    cantidad_disponible = models.DecimalField(max_digits=12, decimal_places=3, default=0)
    fecha_actualizacion = models.DateTimeField(auto_now=True, editable=False)  # <-- clave

    class Meta:
        db_table = "insumo"
        managed = False              # <- IMPORTANTE: no generar migraciones
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre



class Kardex(models.Model):
    insumo = models.ForeignKey(Insumo, models.DO_NOTHING)
    fecha = models.DateTimeField(blank=True, null=True)
    tipo = models.CharField(max_length=7)
    motivo = models.CharField(max_length=7)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)
    observacion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'kardex'


class Pago(models.Model):
    pedido = models.OneToOneField('Pedido', models.DO_NOTHING)
    metodo = models.CharField(max_length=13)
    monto = models.DecimalField(max_digits=12, decimal_places=2)
    referencia = models.CharField(max_length=120, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pago'


class Pedido(models.Model):
    cliente = models.ForeignKey(Cliente, models.DO_NOTHING)
    estado = models.CharField(max_length=10, blank=True, null=True)
    metodo_envio = models.CharField(max_length=20)
    costo_envio = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    direccion_entrega = models.CharField(max_length=200, blank=True, null=True)
    total = models.DecimalField(max_digits=12, decimal_places=2)
    observaciones = models.CharField(max_length=300, blank=True, null=True)
    created_at = models.DateTimeField(blank=True, null=True)
    fecha_entrega_programada = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pedido'


class PedidoDescuento(models.Model):
    pk = models.CompositePrimaryKey('pedido_id', 'descuento_id')
    pedido = models.ForeignKey(Pedido, models.DO_NOTHING)
    descuento = models.ForeignKey(Descuento, models.DO_NOTHING)
    monto_aplicado = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'pedido_descuento'


class Permiso(models.Model):
    codigo = models.CharField(unique=True, max_length=80)
    descripcion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'permiso'


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


class ProductoSabor(models.Model):
    pk = models.CompositePrimaryKey('producto_id', 'sabor_id')
    producto = models.ForeignKey(Producto, models.DO_NOTHING)
    sabor = models.ForeignKey('Sabor', models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'producto_sabor'


class Proveedor(models.Model):
    nombre = models.CharField(max_length=150)
    telefono = models.CharField(max_length=40, blank=True, null=True)
    direccion = models.CharField(max_length=200, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'proveedor'
        ordering = ['nombre']  # opcional: orden alfabético en el combo

    def __str__(self):
        return self.nombre



class Receta(models.Model):
    pk = models.CompositePrimaryKey('producto_id', 'insumo_id')
    producto = models.ForeignKey(Producto, models.DO_NOTHING)
    insumo = models.ForeignKey(Insumo, models.DO_NOTHING)
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        managed = False
        db_table = 'receta'


class Rol(models.Model):
    nombre = models.CharField(unique=True, max_length=80)

    class Meta:
        managed = False
        db_table = 'rol'


class RolPermiso(models.Model):
    id = models.BigAutoField(primary_key=True)  # <- ahora PK simple
    rol = models.ForeignKey('Rol', on_delete=models.PROTECT, db_column='rol_id')
    permiso = models.ForeignKey('Permiso', on_delete=models.PROTECT, db_column='permiso_id')

    class Meta:
        managed = False
        db_table = 'rol_permiso'
        unique_together = (('rol', 'permiso'),)


class Sabor(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=100)
    activo = models.IntegerField()
    imagen = models.CharField(
        max_length=200, blank=True, null=True, db_column="imagen"
    )  # <<-- NUEVO

    class Meta:
        managed = False
        db_table = 'sabor'


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


class UsuarioRol(models.Model):
    id = models.BigAutoField(primary_key=True)  # <- ahora PK simple
    usuario = models.ForeignKey('Usuario', on_delete=models.PROTECT, db_column='usuario_id')
    rol = models.ForeignKey('Rol', on_delete=models.PROTECT, db_column='rol_id')

    class Meta:
        managed = False
        db_table = 'usuario_rol'
        unique_together = (('usuario', 'rol'),)
