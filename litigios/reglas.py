"""Reglas de negocio del prototipo, como funciones puras (sin base de datos). Cada una tiene pruebas en
tests/test_reglas.py. Si cambias algo aquí, compara primero con docs/referencia/prototipo.html."""

from nucleo.fechas import dias_hasta, fmt

from .catalogos import FLUJO_ACC

TIPOS_QUE_ESPERAN_AUTO = ("Promoción", "Escrito")


# ---------- semáforo ----------
def plazo_chip(fecha, ref=None):
    """plazoChip(): (clase, texto) para el plazo de una acción, o None si no tiene plazo."""
    n = dias_hasta(fecha, ref)
    if n is None:
        return None
    if n < 0:
        return "red", f"Venció {fmt(fecha, ref=ref)}"
    if n == 0:
        return "red", "Vence hoy"
    if n == 1:
        return "red", "Vence mañana"
    if n <= 3:
        return "red", f"Vence en {n} días"
    if n <= 7:
        return "amb", f"Vence en {n} días"
    return "blu", f"Vence {fmt(fecha, ref=ref)}"


def estilo_plazo(fecha, terminada, ref=None):
    """Color del plazo en la tabla de acciones: rojo a 3 días, ámbar a 7 (solo si no está terminada)."""
    n = dias_hasta(fecha, ref)
    if terminada or n is None:
        return ""
    if n <= 3:
        return "color:var(--red-t);font-weight:600"
    if n <= 7:
        return "color:var(--amb-t);font-weight:600"
    return ""


def urgencia(proximo_plazo, dias_sin_actuacion, ref=None):
    """urgencia(): {'cls','txt','orden'} o None.
    Orden de evaluación: plazo ≤3 (rojo) · >60 días sin actuación (rojo) · plazo ≤7 (ámbar) · >30 días (ámbar)."""
    n = dias_hasta(proximo_plazo, ref)
    ds = dias_sin_actuacion
    if n is not None and n <= 3:
        txt = (
            "Plazo vencido" if n < 0 else "Vence hoy" if n == 0 else "Vence mañana" if n == 1 else f"Vence en {n} días"
        )
        return {"cls": "red", "txt": txt, "orden": n}
    if ds is not None and ds > 60:
        return {"cls": "red", "txt": f"{ds} días sin actuación", "orden": -1}
    if n is not None and n <= 7:
        return {"cls": "amb", "txt": f"Vence en {n} días", "orden": n}
    if ds is not None and ds > 30:
        return {"cls": "amb", "txt": f"{ds} días sin actuación", "orden": 50}
    return None


def plazo_en_rojo(fecha, ref=None):
    n = dias_hasta(fecha, ref)
    return n is not None and n <= 3


# ---------- flujo de acciones ----------
def siguiente_estado(estado):
    i = FLUJO_ACC.index(estado)
    return FLUJO_ACC[i + 1] if i + 1 < len(FLUJO_ACC) else None


def puede_terminar(estado, tiene_revisor, tiene_aprobador):
    """Solo se termina una acción aprobada, o una sin revisor ni aprobador que ya no esté pendiente."""
    if estado == "terminada":
        return False
    return estado == "aprobada" or (not tiene_revisor and not tiene_aprobador and estado != "pendiente")


ETIQUETA_AVANCE = {"elaboracion": "Iniciar", "revision": "A revisión", "aprobada": "Aprobar"}


def boton_accion(estado, tiene_revisor, tiene_aprobador):
    """Qué botón muestra la fila: ('terminar', 'Terminar'), ('avanzar', etiqueta) o None."""
    if estado == "terminada":
        return None
    if puede_terminar(estado, tiene_revisor, tiene_aprobador):
        return "terminar", "Terminar"
    nxt = siguiente_estado(estado)
    if nxt and nxt != "terminada":
        return "avanzar", ETIQUETA_AVANCE[nxt]
    return None


def puede_aprobar(usuario, aprueba_id, revisa_id):
    """Decisión #1 (propuesta adoptada): si la acción tiene aprobador, aprueba cualquier usuario con rol
    'aprueba' (si no es el asignado se pide confirmación y queda en auditoría). Si no tiene aprobador,
    también puede darla por aprobada su revisor."""
    if usuario.puede_aprobar:
        return True
    return not aprueba_id and revisa_id == usuario.pk


def espera_auto_al_terminar(tipo):
    return tipo in TIPOS_QUE_ESPERAN_AUTO


# ---------- equipo y tareas ----------
def rol_en_tarea(estado, usuario_id, responsable_id, revisa_id, aprueba_id):
    """Traducción literal de la expresión de VIEWS.equipo del prototipo."""
    n = usuario_id
    if estado == "revision" and revisa_id == n:
        return "Revisar"
    if estado == "aprobada" and responsable_id == n:
        return "Presentar"
    if estado in ("revision", "aprobada") and aprueba_id == n and estado == "revision" and not revisa_id:
        return "Aprobar"
    if estado == "revision" and aprueba_id == n and revisa_id == n:
        return "Revisar y aprobar"
    if responsable_id == n and estado in ("pendiente", "elaboracion"):
        return "Elaborar"
    return None


def clase_por_plazo(fecha, ref=None):
    n = dias_hasta(fecha, ref)
    if n is not None and n <= 3:
        return "red"
    if n is not None and n <= 7:
        return "amb"
    return "blu"


# ---------- recursos ----------
def chip_recurso(estado, resultado, promovente):
    if estado == "resuelto":
        if resultado.startswith("Favorable"):
            cls = "grn"
        elif any(x in resultado for x in ("Desfavorable", "Desechado", "Sobrese")):
            cls = "red"
        else:
            cls = "gry"
        return cls, resultado or "Resuelto"
    return ("blu", "Lo promovimos") if promovente == "Nosotros" else ("amb", "De la contraparte")


def chip_suspension(tipo, suspension):
    if tipo != "Amparo indirecto" or not suspension or suspension == "No aplica":
        return None
    cls = "grn" if "concedida" in suspension else "red" if suspension == "Negada" else "gry"
    return cls, f"Suspensión {suspension.lower()}"


def etapa_expediente_por_recurso(tipo, etapa_actual):
    if "amparo" in tipo.lower():
        return "Amparo"
    if tipo == "Apelación":
        return "Apelación"
    return etapa_actual
