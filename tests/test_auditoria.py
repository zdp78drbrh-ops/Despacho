import pytest
from django.db import connection, transaction

from auditoria.models import EventoAuditoria
from auditoria.servicios import Actor, auditar, verificar_cadena
from litigios.models import EntradaBitacora


def test_cadena_integra_y_sellada_por_la_base(db):
    for i in range(3):
        auditar(Actor(), "prueba", None, entidad="x", entidad_id=i, datos={"n": i})
    evs = list(EventoAuditoria.objects.order_by("id"))
    assert all(len(e.hash) == 64 and e.fecha for e in evs)
    assert evs[1].hash_anterior == evs[0].hash and evs[2].hash_anterior == evs[1].hash
    assert verificar_cadena() is None


@pytest.mark.parametrize(
    "sql",
    [
        "UPDATE auditoria_eventoauditoria SET accion='x'",
        "DELETE FROM auditoria_eventoauditoria",
        "TRUNCATE auditoria_eventoauditoria",
    ],
)
def test_la_base_rechaza_modificar_o_borrar(db, sql):
    auditar(Actor(), "prueba", None, entidad="x")
    with connection.cursor() as c:  # las FK de Django son diferidas; se resuelven antes de probar TRUNCATE
        c.execute("SET CONSTRAINTS ALL IMMEDIATE")
    with pytest.raises(Exception, match="solo alta"), transaction.atomic(), connection.cursor() as c:
        c.execute(sql)


def test_orm_tampoco_puede(db):
    ev = auditar(Actor(), "prueba", None, entidad="x")
    ev.accion = "otra"
    with pytest.raises(Exception, match="solo alta"), transaction.atomic():
        ev.save()
    with pytest.raises(Exception, match="solo alta"), transaction.atomic():
        ev.delete()


def test_alteracion_detectada(db):
    auditar(Actor(), "a", None, entidad="x")
    ev = auditar(Actor(), "b", None, entidad="x")
    auditar(Actor(), "c", None, entidad="x")
    with connection.cursor() as c:  # un superusuario que desactiva el trigger
        c.execute("SET CONSTRAINTS ALL IMMEDIATE")
        c.execute("ALTER TABLE auditoria_eventoauditoria DISABLE TRIGGER inmutable")
        c.execute("UPDATE auditoria_eventoauditoria SET descripcion='maquillado' WHERE id=%s", [ev.id])
    assert verificar_cadena() == ev.id


def test_bitacora_visible_es_solo_alta(expediente):
    b = expediente.bitacora.first()
    with pytest.raises(Exception, match="solo alta"), transaction.atomic():
        EntradaBitacora.objects.filter(pk=b.pk).update(texto="otro")
