from urllib.parse import quote

from django.shortcuts import redirect

LIBRES = ("/entrar/", "/contrasena/recuperar", "/contrasena/restablecer", "/static/", "/salud/")


class LoginObligatorioMiddleware:
    """Todo el sistema requiere sesión, salvo el acceso y la recuperación de contraseña."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated and not request.path.startswith(LIBRES):
            return redirect(f"/entrar/?next={quote(request.get_full_path())}")
        return self.get_response(request)
