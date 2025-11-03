# accounts/models_recetas.py
from django.db import models
from .models_db import Producto, Insumo  # importas los existentes (no redefinir)

class Receta(models.Model):
    producto = models.ForeignKey(
        Producto,
        on_delete=models.CASCADE,
        db_column='producto_id',
        related_name='recetas',
    )
    insumo = models.ForeignKey(
        Insumo,
        on_delete=models.RESTRICT,
        db_column='insumo_id',
        related_name='recetas',
    )
    # Cantidad de insumo por UNIDAD del producto
    cantidad = models.DecimalField(max_digits=12, decimal_places=3)

    class Meta:
        db_table = 'receta'           # usa la tabla que ya creaste en MySQL
        managed = False               # no generes migraciones de esta tabla
        unique_together = (('producto', 'insumo'),)

    def __str__(self):
        return f"{self.producto_id} · {self.insumo_id} · {self.cantidad}"
