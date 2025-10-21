from django.contrib.auth.models import AbstractUser
from django.db import models
from .models_db import *


class User(AbstractUser):
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=40, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username']

    def __str__(self):
        return self.email