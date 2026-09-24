"""Formato de fechas y cómputo de días, igual que las utilidades del prototipo (fmt, fmtLong, addBusinessDays)."""

from datetime import date, timedelta

from django.utils import timezone

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MESES_LARGOS = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]
DIAS = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]  # date.weekday()


def hoy():
    return timezone.localdate()


def fmt(d, con_anio=False, ref=None):
    """'24 sep' — con año si se pide o si no es el año en curso."""
    if not d:
        return "—"
    ref = ref or hoy()
    anio = con_anio or d.year != ref.year
    return f"{d.day} {MESES[d.month - 1]}{' ' + str(d.year) if anio else ''}"


def fmt_largo(d):
    if not d:
        return ""
    return f"{DIAS[d.weekday()]} {d.day} de {MESES_LARGOS[d.month - 1]} de {d.year}"


def dias_hasta(d, ref=None):
    if not d:
        return None
    return (d - (ref or hoy())).days


def dias_desde(d, ref=None):
    n = dias_hasta(d, ref)
    return None if n is None else -n


def sumar_dias_habiles(desde: date, n: int, inhabiles=frozenset()) -> date:
    """Cuenta n días hábiles a partir del día siguiente a `desde`, sin sábados, domingos ni `inhabiles`."""
    d = desde
    c = 0
    while c < n:
        d += timedelta(days=1)
        if d.weekday() < 5 and d not in inhabiles:
            c += 1
    return d
