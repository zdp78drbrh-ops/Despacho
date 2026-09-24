import secrets

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import get_object_or_404, render
from django.urls import reverse

from auditoria.servicios import Actor, auditar, diferencias, foto
from litigios.views import _listo, _modal

from .forms import UsuarioForm


def _solo_admin(request):
    if not request.user.es_admin:
        raise PermissionDenied


def configuracion(request):
    return render(request, "cuentas/configuracion.html", {"usuarios": get_user_model().objects.all()})


def _invitar(request, u):
    """Envía el correo para que la persona defina su contraseña (flujo de 'olvidé mi contraseña')."""
    f = PasswordResetForm({"email": u.email})
    if f.is_valid():
        f.save(
            request=request,
            use_https=request.is_secure(),
            subject_template_name="registration/invitacion_asunto.txt",
            email_template_name="registration/invitacion_correo.txt",
        )


def usuario_nuevo(request):
    _solo_admin(request)
    form = UsuarioForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        with transaction.atomic():
            u = get_user_model().objects.create_user(
                d["email"],
                d["nombre"],
                secrets.token_urlsafe(32),
                rol=d["rol"],
                is_staff=d["is_staff"],
                is_active=d["is_active"],
            )
            auditar(Actor.de(request), "crear", u, datos={k: v for k, v in foto(u).items() if k != "password"})
        _invitar(request, u)
        return _listo(request, reverse("configuracion"), f"Se envió la invitación a {u.email}")
    return _modal(request, form, "Integrante del equipo")


def usuario_editar(request, pk):
    _solo_admin(request)
    u = get_object_or_404(get_user_model(), pk=pk)
    campos = ["nombre", "email", "rol", "is_staff", "is_active"]
    form = UsuarioForm(request.POST or None, instancia=u, initial={k: getattr(u, k) for k in campos})
    if request.method == "POST" and form.is_valid():
        if u == request.user and (not form.cleaned_data["is_staff"] or not form.cleaned_data["is_active"]):
            form.add_error(None, "No puedes quitarte a ti mismo la administración ni desactivarte.")
        else:
            with transaction.atomic():
                antes = foto(u)
                for k in campos:
                    setattr(u, k, form.cleaned_data[k])
                u.save()
                dif = {k: v for k, v in diferencias(antes, foto(u)).items() if k != "password"}
                auditar(Actor.de(request), "editar", u, datos=dif)
            return _listo(request, reverse("configuracion"))
    return _modal(request, form, "Editar integrante")


def usuario_reenviar(request, pk):
    _solo_admin(request)
    if request.method != "POST":
        raise PermissionDenied
    u = get_object_or_404(get_user_model(), pk=pk)
    _invitar(request, u)
    auditar(Actor.de(request), "enviar_acceso", u)
    messages.success(request, f"Se envió el enlace de acceso a {u.email}")
    return _listo(request, reverse("configuracion"))
