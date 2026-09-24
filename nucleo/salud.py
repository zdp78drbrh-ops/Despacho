from django.db import connection
from django.http import HttpResponse


class SaludMiddleware:
    """/salud/ para el chequeo del hosting. Va antes de todo: el chequeo entra por HTTP y con la IP interna como
    Host, así que no debe pasar por la redirección a HTTPS ni por ALLOWED_HOSTS."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path == "/salud/":
            with connection.cursor() as c:
                c.execute("SELECT 1")
            return HttpResponse("ok", content_type="text/plain")
        return self.get_response(request)
