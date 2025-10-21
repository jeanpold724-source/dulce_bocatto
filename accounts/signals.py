# accounts/signals.py
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.dispatch import receiver
from .utils import log_event

@receiver(user_logged_in)
def _log_login(sender, request, user, **kwargs):
    log_event(request, "Auth", getattr(user, "id", 0), "Login")

@receiver(user_logged_out)
def _log_logout(sender, request, user, **kwargs):
    log_event(request, "Auth", getattr(user, "id", 0), "Logout")
