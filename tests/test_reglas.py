"""Reglas puras del prototipo (CLAUDE.md §2)."""

from datetime import date, timedelta

import pytest

from litigios import reglas
from nucleo.fechas import fmt, fmt_largo, sumar_dias_habiles

HOY = date(2026, 9, 24)  # jueves


def d(n):
    return HOY + timedelta(days=n)


@pytest.mark.parametrize(
    "n,esperado",
    [
        (-2, ("red", "Venció 22 sep")),
        (0, ("red", "Vence hoy")),
        (1, ("red", "Vence mañana")),
        (3, ("red", "Vence en 3 días")),
        (4, ("amb", "Vence en 4 días")),
        (7, ("amb", "Vence en 7 días")),
        (8, ("blu", "Vence 2 oct")),
    ],
)
def test_plazo_chip(n, esperado):
    assert reglas.plazo_chip(d(n), HOY) == esperado


def test_plazo_chip_sin_fecha():
    assert reglas.plazo_chip(None, HOY) is None


@pytest.mark.parametrize(
    "plazo,sin,esperado",
    [
        (3, 10, {"cls": "red", "txt": "Vence en 3 días", "orden": 3}),
        (-1, None, {"cls": "red", "txt": "Plazo vencido", "orden": -1}),
        (None, 61, {"cls": "red", "txt": "61 días sin actuación", "orden": -1}),
        (5, 90, {"cls": "red", "txt": "90 días sin actuación", "orden": -1}),  # >60 gana a plazo ámbar
        (5, 10, {"cls": "amb", "txt": "Vence en 5 días", "orden": 5}),
        (None, 31, {"cls": "amb", "txt": "31 días sin actuación", "orden": 50}),
        (None, 30, None),
        (8, 60, {"cls": "amb", "txt": "60 días sin actuación", "orden": 50}),
        (8, 5, None),
    ],
)
def test_urgencia(plazo, sin, esperado):
    assert reglas.urgencia(d(plazo) if plazo is not None else None, sin, HOY) == esperado


def test_estilo_plazo():
    assert "red" in reglas.estilo_plazo(d(3), False, HOY)
    assert "amb" in reglas.estilo_plazo(d(7), False, HOY)
    assert reglas.estilo_plazo(d(8), False, HOY) == ""
    assert reglas.estilo_plazo(d(1), True, HOY) == ""


def test_flujo_de_estados():
    assert [reglas.siguiente_estado(e) for e in ["pendiente", "elaboracion", "revision", "aprobada", "terminada"]] == [
        "elaboracion",
        "revision",
        "aprobada",
        "terminada",
        None,
    ]


@pytest.mark.parametrize(
    "estado,rev,apr,esperado",
    [
        ("aprobada", True, True, True),
        ("revision", True, True, False),
        ("elaboracion", True, False, False),
        ("elaboracion", False, False, True),
        ("pendiente", False, False, False),
        ("terminada", False, False, False),
        ("revision", False, False, True),
    ],
)
def test_puede_terminar(estado, rev, apr, esperado):
    assert reglas.puede_terminar(estado, rev, apr) is esperado


@pytest.mark.parametrize(
    "estado,rev,apr,esperado",
    [
        ("pendiente", True, True, ("avanzar", "Iniciar")),
        ("elaboracion", True, True, ("avanzar", "A revisión")),
        ("revision", True, True, ("avanzar", "Aprobar")),
        ("aprobada", True, True, ("terminar", "Terminar")),
        ("pendiente", False, False, ("avanzar", "Iniciar")),
        ("elaboracion", False, False, ("terminar", "Terminar")),
        ("terminada", True, True, None),
    ],
)
def test_boton(estado, rev, apr, esperado):
    assert reglas.boton_accion(estado, rev, apr) == esperado


def test_espera_auto_solo_promocion_y_escrito():
    assert reglas.espera_auto_al_terminar("Promoción") and reglas.espera_auto_al_terminar("Escrito")
    assert not any(reglas.espera_auto_al_terminar(t) for t in ["Acto procesal", "Diligencia", "Gestión", "Audiencia"])


def test_rol_en_tarea():
    assert reglas.rol_en_tarea("revision", 2, 1, 2, 3) == "Revisar"
    assert reglas.rol_en_tarea("aprobada", 1, 1, 2, 3) == "Presentar"
    assert reglas.rol_en_tarea("revision", 3, 1, None, 3) == "Aprobar"
    assert reglas.rol_en_tarea("elaboracion", 1, 1, 2, 3) == "Elaborar"
    assert reglas.rol_en_tarea("revision", 3, 1, 2, 3) is None  # aprobador espera a que el revisor termine


def test_chips_recurso():
    assert reglas.chip_recurso("tramite", "", "Nosotros") == ("blu", "Lo promovimos")
    assert reglas.chip_recurso("tramite", "", "Contraparte") == ("amb", "De la contraparte")
    assert reglas.chip_recurso("resuelto", "Favorable", "Nosotros") == ("grn", "Favorable")
    assert reglas.chip_recurso("resuelto", "Parcialmente favorable", "Nosotros")[0] == "gry"
    assert reglas.chip_recurso("resuelto", "Sobreseído", "Nosotros")[0] == "red"
    assert reglas.chip_suspension("Amparo indirecto", "Definitiva concedida") == (
        "grn",
        "Suspensión definitiva concedida",
    )
    assert reglas.chip_suspension("Amparo indirecto", "Negada")[0] == "red"
    assert reglas.chip_suspension("Amparo directo", "Negada") is None
    assert reglas.chip_suspension("Amparo indirecto", "No aplica") is None


def test_etapa_por_recurso():
    assert reglas.etapa_expediente_por_recurso("Amparo directo", "Sentencia") == "Amparo"
    assert reglas.etapa_expediente_por_recurso("Apelación", "Sentencia") == "Apelación"
    assert reglas.etapa_expediente_por_recurso("Queja", "Sentencia") == "Sentencia"


def test_fechas():
    assert fmt(date(2026, 9, 24), ref=HOY) == "24 sep"
    assert fmt(date(2025, 3, 12), ref=HOY) == "12 mar 2025"
    assert fmt(date(2026, 9, 24), True, ref=HOY) == "24 sep 2026"
    assert fmt_largo(HOY) == "jueves 24 de septiembre de 2026"


def test_dias_habiles():
    assert sumar_dias_habiles(HOY, 1) == date(2026, 9, 25)  # viernes
    assert sumar_dias_habiles(HOY, 2) == date(2026, 9, 28)  # salta fin de semana
    assert sumar_dias_habiles(HOY, 2, {date(2026, 9, 28)}) == date(2026, 9, 29)
