"""Vistas: acceso, permisos, archivos y pantallas."""

from datetime import timedelta

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from auditoria.models import EventoAuditoria
from litigios.management.commands.cargar_ejemplo import cargar
from litigios.models import Accion, Documento
from nucleo.fechas import hoy

PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture(autouse=True)
def media_temporal(settings, tmp_path):
    settings.STORAGES = {
        **settings.STORAGES,
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage", "OPTIONS": {"location": str(tmp_path)}},
    }


def test_todo_requiere_sesion(client, db):
    r = client.get("/litigios/")
    assert r.status_code == 302 and r["Location"].startswith("/entrar/")
    assert client.get("/entrar/").status_code == 200


def test_login_audita_y_bloquea(client, usuarios):
    assert client.post("/entrar/", {"username": "m@x.mx", "password": "clave-de-prueba-123"}).status_code == 302
    assert EventoAuditoria.objects.filter(accion="iniciar_sesion").exists()
    client.logout()
    for _ in range(5):
        client.post("/entrar/", {"username": "m@x.mx", "password": "mala"})
    r = client.post("/entrar/", {"username": "m@x.mx", "password": "clave-de-prueba-123"})
    assert r.status_code == 200  # bloqueada aunque la contraseña sea correcta
    assert EventoAuditoria.objects.filter(accion="acceso_fallido").count() >= 5


@pytest.mark.parametrize(
    "url",
    [
        "/litigios/",
        "/expedientes/",
        "/expedientes/urgentes/",
        "/expedientes/sentencia/",
        "/expedientes/terminados/",
        "/acuerdos/",
        "/recursos/",
        "/calendario/",
        "/equipo/",
        "/configuracion/",
        "/configuracion/auditoria/",
        "/corporativo/",
    ],
)
def test_pantallas_con_datos_de_ejemplo(client, db, url):
    usuarios = cargar()
    client.force_login(usuarios["Abraham Jassen"])
    assert client.get(url).status_code == 200


def test_ficha_y_modales(cliente_web, expediente):
    c = cliente_web("M")
    r = c.get(reverse("expediente", args=[expediente.pk]))
    assert r.status_code == 200 and "Próximas acciones a realizar" in r.content.decode()
    for nombre in [
        "expediente_editar",
        "expediente_etapa",
        "expediente_estado",
        "expediente_informe",
        "accion_nueva",
        "documento_nuevo",
        "bitacora_nueva",
        "recurso_nuevo_exp",
    ]:
        r = c.get(reverse(nombre, args=[expediente.pk]), HTTP_X_REQUESTED_WITH="fetch")
        assert r.status_code == 200, nombre
        assert "<html" not in r.content.decode()


def test_modal_con_errores_y_redireccion(cliente_web, expediente):
    c = cliente_web("M")
    url = reverse("accion_nueva", args=[expediente.pk])
    r = c.post(url, {"tipo": "Promoción"}, HTTP_X_REQUESTED_WITH="fetch")
    assert "Falta: Documento, promoción o acto" in r.content.decode()
    r = c.post(url, {"titulo": "Contestar", "tipo": "Promoción"}, HTTP_X_REQUESTED_WITH="fetch")
    assert r.status_code == 204 and r["X-Despacho-Redirect"] == reverse("expediente", args=[expediente.pk])


def test_subir_y_descargar_pdf(cliente_web, expediente):
    c = cliente_web("D")
    url = reverse("documento_nuevo", args=[expediente.pk])
    r = c.post(
        url,
        {
            "nombre": "06 Auto",
            "fecha": hoy().isoformat(),
            "archivo": SimpleUploadedFile("a.pdf", PDF, "application/pdf"),
        },
        HTTP_X_REQUESTED_WITH="fetch",
    )
    assert r.status_code == 204
    d = Documento.objects.get(nombre="06 Auto")
    assert d.archivo.name.startswith(f"clientes/{expediente.cliente_id}/expedientes/{expediente.id}/")
    assert len(d.sha256) == 64
    r = c.get(reverse("documento_descargar", args=[d.pk]))
    assert r.status_code == 200 and b"".join(r.streaming_content) == PDF
    assert EventoAuditoria.objects.filter(accion="descargar_archivo", entidad_id=str(d.pk)).exists()


def test_rechaza_lo_que_no_es_pdf(cliente_web, expediente):
    c = cliente_web("D")
    r = c.post(
        reverse("documento_nuevo", args=[expediente.pk]),
        {
            "nombre": "x",
            "fecha": hoy().isoformat(),
            "archivo": SimpleUploadedFile("x.pdf", b"MZ\x90 no es pdf", "application/pdf"),
        },
        HTTP_X_REQUESTED_WITH="fetch",
    )
    assert "Solo se aceptan archivos PDF" in r.content.decode()
    assert not Documento.objects.filter(nombre="x").exists()


def test_boton_aprobar_desactivado_para_quien_no_aprueba(cliente_web, expediente, usuarios):
    Accion.objects.create(
        expediente=expediente,
        titulo="Escrito",
        tipo="Escrito",
        estado="revision",
        revisa=usuarios["Y"],
        aprueba=usuarios["A"],
        plazo=hoy() + timedelta(days=2),
    )
    html = cliente_web("M").get(reverse("expediente", args=[expediente.pk])).content.decode()
    assert 'disabled title="Solo quien aprueba">Aprobar' in html
    html = cliente_web("A2").get(reverse("expediente", args=[expediente.pk])).content.decode()
    assert "¿Aprobar de todos modos como Otra Socia?" in html


def test_solo_admin_administra_usuarios(cliente_web, usuarios):
    assert cliente_web("M").get(reverse("usuario_nuevo")).status_code == 403
    c = cliente_web("A")
    r = c.post(
        reverse("usuario_nuevo"),
        {"nombre": "Lic. Nueva", "email": "nueva@x.mx", "rol": "elabora", "is_active": "on"},
        HTTP_X_REQUESTED_WITH="fetch",
    )
    assert r.status_code == 204
    from django.core import mail

    assert mail.outbox and "nueva@x.mx" in mail.outbox[0].to


def test_auditoria_solo_para_quien_aprueba_o_admin(cliente_web, usuarios):
    assert cliente_web("D").get(reverse("auditoria")).status_code == 403
    assert cliente_web("A2").get(reverse("auditoria") + "?verificar=1").status_code == 200


def test_calcular_plazo(cliente_web, usuarios):
    r = cliente_web("M").get("/plazo/calcular/?dias=2&desde=2026-09-24")
    assert r.json() == {"fecha": "2026-09-28"}
    assert cliente_web("M").get("/plazo/calcular/?dias=0").status_code == 400


def test_informe_al_cliente(cliente_web, expediente):
    r = cliente_web("M").get(reverse("expediente_informe", args=[expediente.pk]), HTTP_X_REQUESTED_WITH="fetch")
    txt = r.content.decode()
    assert "Le comparto el estado del asunto 312/2025, Oral mercantil" in txt
    assert "Por el momento estamos en espera de que el juzgado acuerde lo conducente." in txt
