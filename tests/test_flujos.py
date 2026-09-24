"""Flujos de Litigios contra la base de datos (servicios)."""

from datetime import timedelta

import pytest
from django.core.exceptions import PermissionDenied

from auditoria.models import EventoAuditoria
from litigios import servicios
from litigios.models import Accion, Documento, Expediente
from nucleo.fechas import hoy


def _accion(expediente, actor, usuarios, **kw):
    datos = {
        "titulo": "Escrito de designación de perito",
        "tipo": "Promoción",
        "responsable": usuarios["M"],
        "revisa": usuarios["Y"],
        "aprueba": usuarios["A"],
        "plazo": hoy() + timedelta(days=3),
        "notas": "",
        "recurso": None,
    }
    datos.update(kw)
    return servicios.crear_accion(actor("M"), expediente, datos)


def test_alta_de_expediente_crea_cliente_bitacora_y_auditoria(expediente):
    assert expediente.cliente.razon == "Constructora del Bajío, S.A. de C.V."
    assert expediente.bitacora.get().texto == "Se dio de alta el expediente"
    assert EventoAuditoria.objects.filter(entidad="expediente", accion="crear").exists()


def test_flujo_completo_con_revision_y_aprobacion(expediente, actor, usuarios):
    a = _accion(expediente, actor, usuarios)
    servicios.avanzar_accion(actor("M"), a)
    assert a.estado == "elaboracion"
    with pytest.raises(PermissionDenied):
        servicios.terminar_accion(actor("M"), a, hoy())
    servicios.avanzar_accion(actor("M"), a)
    assert a.estado == "revision"
    assert expediente.bitacora.filter(texto=f"A revisión: {a.titulo}").exists()
    with pytest.raises(PermissionDenied):  # quien elabora no aprueba
        servicios.avanzar_accion(actor("M"), a)
    with pytest.raises(PermissionDenied):  # quien revisa tampoco, si hay aprobador
        servicios.avanzar_accion(actor("Y"), a)
    servicios.avanzar_accion(actor("A"), a)
    assert a.estado == "aprobada"
    assert expediente.bitacora.filter(texto=f"Aprobado: {a.titulo}").exists()
    assert EventoAuditoria.objects.filter(accion="aprobar", entidad_id=str(a.pk)).exists()


def test_aprobar_en_lugar_de_otro_exige_confirmacion(expediente, actor, usuarios):
    a = _accion(expediente, actor, usuarios)
    Accion.objects.filter(pk=a.pk).update(estado="revision")
    a.refresh_from_db()
    with pytest.raises(PermissionDenied):
        servicios.avanzar_accion(actor("A2"), a)
    servicios.avanzar_accion(actor("A2"), a, confirmado=True)
    ev = EventoAuditoria.objects.get(accion="aprobar", entidad_id=str(a.pk))
    assert ev.datos["aprobo_en_lugar_de"] == "Abraham Jassen"


def test_sin_aprobador_aprueba_el_revisor(expediente, actor, usuarios):
    a = _accion(expediente, actor, usuarios, aprueba=None)
    Accion.objects.filter(pk=a.pk).update(estado="revision")
    a.refresh_from_db()
    servicios.avanzar_accion(actor("Y"), a)
    assert a.estado == "aprobada"


def test_terminar_promocion_deja_esperando_auto_y_acuerdo_lo_quita(expediente, actor, usuarios):
    a = _accion(expediente, actor, usuarios)
    Accion.objects.filter(pk=a.pk).update(estado="aprobada")
    a.refresh_from_db()
    servicios.terminar_accion(actor("M"), a, hoy(), "Acuse 23 sep", registrar_documento=True)
    expediente.refresh_from_db()
    assert a.estado == "terminada" and expediente.esperando_auto
    assert expediente.bitacora.filter(texto=f"{a.titulo} · Acuse 23 sep").exists()
    assert Documento.objects.filter(expediente=expediente, nombre=a.titulo).exists()

    servicios.registrar_acuerdo(
        actor("D"),
        expediente,
        hoy(),
        "Se tiene por designado perito",
        "Desahogar vista",
        hoy() + timedelta(days=3),
        crear=True,
    )
    expediente.refresh_from_db()
    assert not expediente.esperando_auto
    assert expediente.bitacora.filter(texto="Se registró acuerdo: Se tiene por designado perito").exists()
    nueva = expediente.acciones.get(titulo="Desahogar vista")
    assert nueva.tipo == "Promoción" and nueva.estado == "pendiente" and nueva.responsable == usuarios["M"]
    assert nueva.notas.startswith("Derivada del acuerdo del ")


def test_terminar_audiencia_no_deja_esperando_auto(expediente, actor, usuarios):
    a = _accion(expediente, actor, usuarios, tipo="Audiencia", revisa=None, aprueba=None)
    servicios.avanzar_accion(actor("M"), a)
    servicios.terminar_accion(actor("M"), a, hoy())
    expediente.refresh_from_db()
    assert not expediente.esperando_auto


def test_acuerdo_solo_registrar_no_crea_accion(expediente, actor):
    servicios.registrar_acuerdo(actor("D"), expediente, hoy(), "A sus autos", "Solo registrar", None, crear=True)
    assert not expediente.acciones.exists()


def test_etapa_citado_a_sentencia_cambia_estado(expediente, actor):
    servicios.cambiar_etapa(actor("M"), expediente, "Citado a sentencia")
    assert expediente.estado == "sentencia"
    assert expediente.bitacora.filter(texto="Cambió la etapa procesal a: Citado a sentencia").exists()


def test_estado_con_nota(expediente, actor):
    servicios.cambiar_estado_expediente(actor("A"), expediente, "terminado", "Convenio")
    assert expediente.bitacora.filter(texto="Estado: terminado · Convenio").exists()


def test_recurso_completo(expediente, actor, usuarios):
    expediente.estado = "sentencia"
    expediente.save()
    x = servicios.crear_recurso(
        actor("Y"),
        expediente,
        {
            "tipo": "Apelación",
            "promovente": "Contraparte",
            "acto_impugnado": "Sentencia definitiva",
            "numero": "Toca 512/2026",
            "organo": "Segunda Sala",
            "fecha_interposicion": hoy(),
            "etapa": "Interposición del recurso",
            "suspension": "No aplica",
            "notas": "",
        },
    )
    expediente.refresh_from_db()
    assert expediente.etapa == "Apelación" and expediente.estado == "activo"
    assert expediente.bitacora.filter(texto="La contraparte interpuso apelación contra Sentencia definitiva").exists()
    servicios.mover_etapa_recurso(actor("Y"), x, 1)
    assert x.etapa == "Admisión y efectos"
    assert expediente.bitacora.filter(texto="Apelación · Toca 512/2026: Admisión y efectos").exists()
    servicios.mover_etapa_recurso(actor("Y"), x, -1)
    servicios.mover_etapa_recurso(actor("Y"), x, -1)  # no baja de la primera
    assert x.etapa == "Interposición del recurso"
    a = _accion(expediente, actor, usuarios, recurso=x)
    servicios.resolver_recurso(actor("A"), x, "Favorable", hoy(), "Se confirma", "Ejecución")
    x.refresh_from_db()
    a.refresh_from_db()
    expediente.refresh_from_db()
    assert x.estado == "resuelto" and x.etapa == "Devolución al juzgado de origen" and expediente.etapa == "Ejecución"
    assert a.notas.endswith("Recurso resuelto, revisar si sigue pendiente")
    servicios.reabrir_recurso(actor("A"), x)
    assert x.estado == "tramite" and x.resultado == ""
    servicios.eliminar_recurso(actor("A"), x)
    a.refresh_from_db()
    assert a.recurso is None and not expediente.recursos.exists()


def test_bajas_logicas(expediente, actor, usuarios):
    a = _accion(expediente, actor, usuarios)
    servicios.eliminar_accion(actor("M"), a)
    assert not expediente.acciones.exists() and Accion.todos.filter(pk=a.pk).exists()
    with pytest.raises(PermissionDenied):
        servicios.eliminar_expediente(actor("M"), expediente)
    servicios.eliminar_expediente(actor("A"), expediente)
    assert not Expediente.objects.exists() and Expediente.todos.exists()


def test_edicion_no_se_salta_la_aprobacion(expediente, actor, usuarios):
    a = _accion(expediente, actor, usuarios)
    assert "aprobada" not in servicios.estados_permitidos_en_edicion(actor("M"), a)
    with pytest.raises(PermissionDenied):
        servicios.editar_accion(actor("M"), a, {"estado": "aprobada"})
    with pytest.raises(PermissionDenied):
        servicios.editar_accion(actor("A"), a, {"estado": "terminada"})


def test_urgencia_del_expediente(expediente, actor, usuarios):
    assert expediente.urgencia() is None
    _accion(expediente, actor, usuarios, plazo=hoy() + timedelta(days=1))
    e = Expediente.objects.prefetch_related("acciones", "bitacora", "recursos").get(pk=expediente.pk)
    assert e.urgencia() == {"cls": "red", "txt": "Vence mañana", "orden": 1}


def test_importar_respaldo_del_prototipo(db):
    """El JSON se generó abriendo docs/referencia/prototipo.html y exportando sus datos de ejemplo."""
    import json
    from pathlib import Path

    from litigios.management.commands.importar_prototipo import importar

    datos = json.loads((Path(__file__).parent / "datos" / "prototipo_ejemplo.json").read_text(encoding="utf-8"))
    # Ese archivo es la versión sin recursos; se agrega uno con el formato de la versión con apelaciones y amparos.
    e1 = datos["expedientes"][0]
    e1["recursos"] = [
        {
            "id": "r1",
            "tipo": "Apelación",
            "promovente": "Contraparte",
            "numero": "Toca 512/2026",
            "etapa": "Contestación de agravios",
            "estado": "tramite",
            "suspension": "No aplica",
        }
    ]
    e1["acciones"][0]["recursoId"] = "r1"
    r = importar(datos)
    assert r["Expedientes importados"] == 8 and r["Acuerdos importados"] == 4
    exp1 = Expediente.objects.get(numero=e1["numero"])
    x = exp1.recursos.get()
    assert x.tipo == "Apelación" and exp1.acciones.get(titulo=e1["acciones"][0]["titulo"]).recurso == x
    assert Expediente.objects.get(numero="140/2026").esperando_auto
    from django.contrib.auth import get_user_model

    a = get_user_model().objects.get(nombre="Abraham Jassen")
    assert a.rol == "aprueba" and not a.is_active
    assert importar(datos)["Expedientes omitidos (ya existían)"] == 8
