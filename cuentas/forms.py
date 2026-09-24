from django import forms
from django.contrib.auth import get_user_model

from litigios.forms import FormDespacho

from .models import Rol


class UsuarioForm(FormDespacho):
    mitades = {"rol", "is_staff"}
    placeholders = {"nombre": "Lic. Nombre Apellido"}

    nombre = forms.CharField(label="Nombre", max_length=120)
    email = forms.EmailField(label="Correo")
    rol = forms.ChoiceField(label="Rol", choices=Rol.choices)
    is_staff = forms.BooleanField(label="Administra el equipo y la configuración", required=False)
    is_active = forms.BooleanField(label="Activo (puede entrar al sistema)", required=False, initial=True)

    def __init__(self, *a, instancia=None, **kw):
        self.instancia = instancia
        super().__init__(*a, **kw)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        qs = get_user_model().objects.filter(email=email)
        if self.instancia:
            qs = qs.exclude(pk=self.instancia.pk)
        if qs.exists():
            raise forms.ValidationError("Ya hay un usuario con ese correo.")
        return email
