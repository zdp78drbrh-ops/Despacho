from django.contrib import admin
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect
from django.urls import include, path


def salud(_request):
    with connection.cursor() as c:
        c.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("", lambda r: redirect("tablero")),
    path("salud/", salud),
    path("admin/", admin.site.urls),
    path("", include("cuentas.urls")),
    path("", include("auditoria.urls")),
    path("", include("litigios.urls")),
]

admin.site.site_header = "Despacho · administración"
admin.site.site_title = "Despacho"
