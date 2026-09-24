from django.urls import path

from . import views

urlpatterns = [path("configuracion/auditoria/", views.auditoria, name="auditoria")]
