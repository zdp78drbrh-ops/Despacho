from django.contrib.auth import views as auth
from django.urls import path, reverse_lazy

from . import views

urlpatterns = [
    path(
        "entrar/",
        auth.LoginView.as_view(template_name="registration/entrar.html", redirect_authenticated_user=True),
        name="entrar",
    ),
    path("salir/", auth.LogoutView.as_view(), name="salir"),
    path(
        "contrasena/cambiar/",
        auth.PasswordChangeView.as_view(
            template_name="registration/cambiar.html", success_url=reverse_lazy("contrasena_cambiada")
        ),
        name="contrasena_cambiar",
    ),
    path(
        "contrasena/cambiada/",
        auth.PasswordChangeDoneView.as_view(template_name="registration/cambiada.html"),
        name="contrasena_cambiada",
    ),
    path(
        "contrasena/recuperar/",
        auth.PasswordResetView.as_view(
            template_name="registration/recuperar.html",
            email_template_name="registration/recuperar_correo.txt",
            subject_template_name="registration/recuperar_asunto.txt",
            success_url=reverse_lazy("contrasena_enviada"),
        ),
        name="contrasena_recuperar",
    ),
    path(
        "contrasena/recuperar/enviado/",
        auth.PasswordResetDoneView.as_view(template_name="registration/recuperar_enviado.html"),
        name="contrasena_enviada",
    ),
    path(
        "contrasena/restablecer/<uidb64>/<token>/",
        auth.PasswordResetConfirmView.as_view(
            template_name="registration/restablecer.html", success_url=reverse_lazy("contrasena_lista")
        ),
        name="password_reset_confirm",
    ),
    path(
        "contrasena/restablecer/listo/",
        auth.PasswordResetCompleteView.as_view(template_name="registration/restablecer_listo.html"),
        name="contrasena_lista",
    ),
    path("configuracion/", views.configuracion, name="configuracion"),
    path("configuracion/usuario/nuevo/", views.usuario_nuevo, name="usuario_nuevo"),
    path("configuracion/usuario/<int:pk>/", views.usuario_editar, name="usuario_editar"),
    path("configuracion/usuario/<int:pk>/reenviar/", views.usuario_reenviar, name="usuario_reenviar"),
]
