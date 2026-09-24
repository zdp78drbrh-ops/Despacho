import csv

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpResponse
from django.shortcuts import render

from .models import EventoAuditoria
from .servicios import verificar_cadena


def auditoria(request):
    """Consulta de solo lectura. La ven administradores y quienes aprueban."""
    if not (request.user.es_admin or request.user.puede_aprobar):
        raise PermissionDenied
    qs = EventoAuditoria.objects.all()
    g = request.GET
    if g.get("usuario"):
        qs = qs.filter(usuario_id=g["usuario"])
    if g.get("entidad"):
        qs = qs.filter(entidad=g["entidad"])
    if g.get("accion"):
        qs = qs.filter(accion=g["accion"])
    if g.get("desde"):
        qs = qs.filter(fecha__date__gte=g["desde"])
    if g.get("hasta"):
        qs = qs.filter(fecha__date__lte=g["hasta"])
    if g.get("q"):
        qs = qs.filter(descripcion__icontains=g["q"]) | qs.filter(entidad_id=g["q"])
    if g.get("csv"):
        r = HttpResponse(content_type="text/csv; charset=utf-8")
        r["Content-Disposition"] = 'attachment; filename="auditoria.csv"'
        r.write("﻿")
        w = csv.writer(r)
        w.writerow(["id", "fecha", "usuario", "ip", "accion", "entidad", "entidad_id", "descripcion", "datos", "hash"])
        for e in qs.iterator():
            w.writerow(
                [
                    e.id,
                    e.fecha.isoformat(),
                    e.usuario_nombre,
                    e.ip or "",
                    e.accion,
                    e.entidad,
                    e.entidad_id,
                    e.descripcion,
                    e.datos,
                    e.hash,
                ]
            )
        return r
    pagina = Paginator(qs, 100).get_page(g.get("p"))
    base = g.copy()
    base.pop("p", None)
    return render(
        request,
        "auditoria/lista.html",
        {
            "pagina": pagina,
            "usuarios": get_user_model().objects.all(),
            "g": g,
            "base": base.urlencode(),
            "entidades": EventoAuditoria.objects.values_list("entidad", flat=True).distinct().order_by("entidad"),
            "acciones": EventoAuditoria.objects.values_list("accion", flat=True).distinct().order_by("accion"),
            "integra": verificar_cadena() is None if g.get("verificar") else None,
        },
    )
