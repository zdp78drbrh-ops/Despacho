from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

urlpatterns = [
    path("", lambda r: redirect("tablero")),
    path("admin/", admin.site.urls),
    path("", include("cuentas.urls")),
    path("", include("auditoria.urls")),
    path("", include("litigios.urls")),
]

admin.site.site_header = "Despacho · administración"
admin.site.site_title = "Despacho"
