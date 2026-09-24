from decimal import Decimal, InvalidOperation

from django import template
from django.utils.html import format_html

from litigios import reglas
from nucleo import fechas

register = template.Library()


@register.filter
def fmt(d, con_anio=False):
    return fechas.fmt(d, bool(con_anio))


@register.filter
def fmt_largo(d):
    return fechas.fmt_largo(d)


@register.filter
def dinero(n):
    """money(): $4,850,000.00 — '—' si está vacío."""
    if n in (None, ""):
        return "—"
    try:
        n = Decimal(n)
    except (InvalidOperation, TypeError):
        return "—"
    return "$" + f"{n:,.2f}"


@register.filter
def iniciales(nombre):
    import re

    n = re.sub(r"^(Lic\.|Ing\.|Arq\.|Dr\.|Dra\.|C\.P\.)\s*", "", str(nombre or ""), flags=re.I)
    return "".join(w[0].upper() for w in n.split()[:2])


@register.simple_tag
def chip(par, estilo=""):
    """Recibe (clase, texto) y pinta <span class="chip clase">texto</span>."""
    if not par:
        return ""
    cls, txt = par
    if estilo:
        return format_html('<span class="chip {}" style="{}">{}</span>', cls, estilo, txt)
    return format_html('<span class="chip {}">{}</span>', cls, txt)


@register.simple_tag
def chip_plazo(fecha):
    return chip(reglas.plazo_chip(fecha))


@register.filter
def dias_hasta(d):
    return fechas.dias_hasta(d)


@register.filter
def recorta(s, n):
    return str(s or "")[: int(n)]


@register.filter
def pista_de(form, nombre):
    return form.pista(nombre) if hasattr(form, "pista") else ""


@register.filter
def prox_accion_recurso(x):
    acc = [a for a in x.acciones.all() if a.estado != "terminada" and a.plazo]
    return min(acc, key=lambda a: a.plazo) if acc else None
