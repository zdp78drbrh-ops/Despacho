"""Todas las escrituras de Litigios pasan por aquí: validan permisos y reglas, escriben la bitácora visible
y la auditoría en la misma transacción. Las vistas no modifican modelos directamente."""

import hashlib

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from auditoria.servicios import auditar, diferencias, foto
from nucleo.fechas import fmt, hoy

from . import reglas
from .catalogos import ESTADOS_EXP, RECURSOS
from .models import Accion, Acuerdo, Cliente, Documento, EntradaBitacora, Expediente, Recurso


# ---------- utilidades ----------
def _bit(actor, e, texto, fecha=None):
    return EntradaBitacora.objects.create(
        expediente=e, fecha=fecha or hoy(), texto=texto, quien=actor.usuario, quien_nombre=actor.nombre
    )


def _guardar_con_auditoria(actor, obj, cambios, accion="editar", descripcion=""):
    antes = foto(obj)
    for k, v in cambios.items():
        setattr(obj, k, v)
    obj.save()
    dif = diferencias(antes, foto(obj))
    if dif:
        auditar(actor, accion, obj, datos=dif, descripcion=descripcion)
    return dif


def _exige_aprueba(actor):
    if not (actor.usuario and actor.usuario.puede_aprobar):
        raise PermissionDenied("Solo quien aprueba puede eliminar.")


def validar_pdf(archivo):
    if archivo.size > settings.PDF_TAMANO_MAXIMO:
        raise ValidationError(f"El archivo supera {settings.PDF_TAMANO_MAXIMO // (1024 * 1024)} MB.")
    archivo.seek(0)
    if archivo.read(5) != b"%PDF-":
        raise ValidationError("Solo se aceptan archivos PDF.")
    archivo.seek(0)
    h = hashlib.sha256()
    for trozo in archivo.chunks():
        h.update(trozo)
    archivo.seek(0)
    return h.hexdigest()


def _poner_pdf(doc, archivo):
    doc.sha256 = validar_pdf(archivo)
    doc.tamano = archivo.size
    doc.archivo.save("x.pdf", archivo, save=False)


def cliente_por_nombre(actor, razon):
    razon = " ".join((razon or "").split())
    c = Cliente.todos.filter(razon__iexact=razon).first()
    if c:
        return c
    c = Cliente.objects.create(razon=razon, responsable=actor.usuario)
    auditar(actor, "crear", c, datos=foto(c))
    return c


# ---------- expedientes ----------
@transaction.atomic
def crear_expediente(actor, datos):
    datos = dict(datos)
    datos["cliente"] = cliente_por_nombre(actor, datos.pop("cliente_nombre"))
    e = Expediente.objects.create(estado="activo", esperando_auto=False, **datos)
    _bit(actor, e, "Se dio de alta el expediente")
    auditar(actor, "crear", e, datos=foto(e))
    return e


@transaction.atomic
def editar_expediente(actor, e, datos):
    datos = dict(datos)
    datos["cliente"] = cliente_por_nombre(actor, datos.pop("cliente_nombre"))
    _guardar_con_auditoria(actor, e, datos)


@transaction.atomic
def cambiar_etapa(actor, e, etapa):
    if etapa == e.etapa:
        return
    cambios = {"etapa": etapa}
    if etapa == "Citado a sentencia":
        cambios["estado"] = "sentencia"
    _bit(actor, e, f"Cambió la etapa procesal a: {etapa}")
    _guardar_con_auditoria(actor, e, cambios, "cambiar_etapa")


@transaction.atomic
def cambiar_estado_expediente(actor, e, estado, nota=""):
    if estado == e.estado:
        return
    etiqueta = {"activo": "activo", "sentencia": "en espera de sentencia", "terminado": "terminado"}[estado]
    _bit(actor, e, f"Estado: {etiqueta}{' · ' + nota if nota else ''}")
    _guardar_con_auditoria(actor, e, {"estado": estado}, "cambiar_estado")


@transaction.atomic
def eliminar_expediente(actor, e):
    _exige_aprueba(actor)
    e.dar_de_baja(actor.usuario)
    auditar(actor, "eliminar", e, descripcion=f"Baja del expediente {e.numero}")


# ---------- acciones ----------
@transaction.atomic
def crear_accion(actor, e, datos):
    a = Accion.objects.create(expediente=e, estado="pendiente", **datos)
    auditar(actor, "crear", a, datos=foto(a))
    return a


def estados_permitidos_en_edicion(actor, a):
    """En 'editar' se puede regresar el estado o avanzar sin saltarse la aprobación. 'Terminada' solo con el botón
    Terminar (pide acuse)."""
    permitidos = []
    for k in ("pendiente", "elaboracion", "revision"):
        permitidos.append(k)
    if a.estado in ("aprobada", "terminada") or reglas.puede_aprobar(actor.usuario, a.aprueba_id, a.revisa_id):
        permitidos.append("aprobada")
    if a.estado == "terminada":
        permitidos.append("terminada")
    return permitidos


@transaction.atomic
def editar_accion(actor, a, datos):
    nuevo = datos.get("estado", a.estado)
    if nuevo != a.estado and nuevo not in estados_permitidos_en_edicion(actor, a):
        raise PermissionDenied("No puedes poner la acción en ese estado desde aquí.")
    _guardar_con_auditoria(actor, a, datos)


@transaction.atomic
def avanzar_accion(actor, a, confirmado=False):
    nxt = reglas.siguiente_estado(a.estado)
    if not nxt or nxt == "terminada":
        return
    e = a.expediente
    datos = {}
    if nxt == "aprobada":
        if not reglas.puede_aprobar(actor.usuario, a.aprueba_id, a.revisa_id):
            raise PermissionDenied("Tu rol no puede aprobar esta acción.")
        if a.aprueba_id and a.aprueba_id != actor.usuario.pk:
            if not confirmado:
                raise PermissionDenied("Falta confirmar la aprobación en nombre de otra persona.")
            datos["aprobo_en_lugar_de"] = a.aprueba.nombre
        _bit(actor, e, f"Aprobado: {a.titulo}")
    if nxt == "revision":
        _bit(actor, e, f"A revisión: {a.titulo}")
    antes = a.estado
    a.estado = nxt
    a.save(update_fields=["estado"])
    auditar(actor, "aprobar" if nxt == "aprobada" else "cambiar_estado", a, datos={"estado": [antes, nxt], **datos})


@transaction.atomic
def terminar_accion(actor, a, fecha, acuse="", registrar_documento=False, archivo=None):
    if not reglas.puede_terminar(a.estado, bool(a.revisa_id), bool(a.aprueba_id)):
        raise PermissionDenied("Solo se puede terminar una acción aprobada (o sin revisor ni aprobador ya iniciada).")
    e = a.expediente
    antes = a.estado
    a.estado, a.acuse, a.terminada_el = "terminada", acuse, fecha
    a.save(update_fields=["estado", "acuse", "terminada_el"])
    _bit(actor, e, f"{a.titulo}{' · ' + acuse if acuse else ''}", fecha)
    if registrar_documento or archivo:
        doc = Documento(expediente=e, nombre=a.titulo, fecha=fecha, quien=actor.usuario, quien_nombre=actor.nombre)
        if archivo:
            _poner_pdf(doc, archivo)
        doc.save()
        auditar(actor, "subir_archivo" if archivo else "crear", doc, datos=foto(doc))
    if reglas.espera_auto_al_terminar(a.tipo) and not e.esperando_auto:
        e.esperando_auto = True
        e.save(update_fields=["esperando_auto"])
    auditar(actor, "terminar", a, datos={"estado": [antes, "terminada"], "acuse": acuse, "fecha": fecha.isoformat()})


@transaction.atomic
def eliminar_accion(actor, a):
    a.dar_de_baja(actor.usuario)
    auditar(actor, "eliminar", a, descripcion=a.titulo)


# ---------- acuerdos ----------
@transaction.atomic
def registrar_acuerdo(actor, e, fecha, sintesis, accion="", plazo=None, crear=True):
    ac = Acuerdo.objects.create(
        expediente=e,
        fecha=fecha,
        sintesis=sintesis,
        accion=accion,
        plazo=plazo,
        registrado_por=actor.usuario,
        registrado_por_nombre=actor.nombre,
    )
    auditar(actor, "crear", ac, datos=foto(ac))
    if e.esperando_auto:
        e.esperando_auto = False
        e.save(update_fields=["esperando_auto"])
    _bit(actor, e, f"Se registró acuerdo: {sintesis}", fecha)
    if crear and accion and accion.lower() != "solo registrar":
        crear_accion(
            actor,
            e,
            {
                "titulo": accion,
                "tipo": "Promoción",
                "responsable": e.responsable or actor.usuario,
                "plazo": plazo,
                "notas": f"Derivada del acuerdo del {fmt(fecha)}",
            },
        )
    return ac


# ---------- documentos y bitácora ----------
@transaction.atomic
def agregar_documento(actor, e, nombre, fecha, archivo=None):
    doc = Documento(expediente=e, nombre=nombre, fecha=fecha, quien=actor.usuario, quien_nombre=actor.nombre)
    if archivo:
        _poner_pdf(doc, archivo)
    doc.save()
    _bit(actor, e, f"Se agregó documento: {nombre}")
    auditar(actor, "subir_archivo" if archivo else "crear", doc, datos=foto(doc))
    return doc


@transaction.atomic
def adjuntar_pdf(actor, doc, archivo):
    antes = foto(doc)
    _poner_pdf(doc, archivo)
    doc.save()
    auditar(actor, "subir_archivo", doc, datos=diferencias(antes, foto(doc)))


@transaction.atomic
def quitar_documento(actor, doc):
    doc.dar_de_baja(actor.usuario)
    auditar(actor, "eliminar", doc, descripcion=doc.nombre)


def registrar_descarga(actor, doc):
    auditar(actor, "descargar_archivo", doc, descripcion=doc.nombre, datos={"sha256": doc.sha256})


@transaction.atomic
def anotar_bitacora(actor, e, texto, fecha):
    b = _bit(actor, e, texto, fecha)
    auditar(actor, "crear", b, datos=foto(b))
    return b


# ---------- recursos ----------
@transaction.atomic
def crear_recurso(actor, e, datos):
    x = Recurso.objects.create(expediente=e, estado="tramite", resultado="", **datos)
    if e.estado != "terminado":
        cambios = {"etapa": reglas.etapa_expediente_por_recurso(x.tipo, e.etapa)}
        if e.estado == "sentencia":
            cambios["estado"] = "activo"
        _guardar_con_auditoria(actor, e, cambios)
    quien = "Interpusimos" if x.promovente == "Nosotros" else "La contraparte interpuso"
    _bit(actor, e, f"{quien} {x.tipo.lower()}{' contra ' + x.acto_impugnado if x.acto_impugnado else ''}")
    auditar(actor, "crear", x, datos=foto(x))
    return x


@transaction.atomic
def editar_recurso(actor, x, datos):
    _guardar_con_auditoria(actor, x, datos)


@transaction.atomic
def mover_etapa_recurso(actor, x, direccion):
    et = RECURSOS.get(x.tipo, {}).get("etapas", [])
    j = (et.index(x.etapa) if x.etapa in et else -1) + direccion
    if j < 0 or j >= len(et):
        return
    if direccion > 0:
        _bit(actor, x.expediente, f"{x.titulo}: {et[j]}")
    _guardar_con_auditoria(actor, x, {"etapa": et[j]}, "cambiar_etapa")


@transaction.atomic
def resolver_recurso(actor, x, resultado, fecha, sintesis, etapa_expediente):
    et = RECURSOS.get(x.tipo, {}).get("etapas", [])
    _guardar_con_auditoria(
        actor,
        x,
        {"estado": "resuelto", "resultado": resultado, "fecha_resolucion": fecha, "etapa": et[-1] if et else x.etapa},
        "resolver",
    )
    e = x.expediente
    _bit(actor, e, f"Se resolvió {x.titulo}: {resultado.lower()}{' · ' + sintesis if sintesis else ''}", fecha)
    _guardar_con_auditoria(actor, e, {"etapa": etapa_expediente})
    for a in x.acciones.exclude(estado="terminada"):
        _guardar_con_auditoria(
            actor, a, {"notas": (a.notas + " · " if a.notas else "") + "Recurso resuelto, revisar si sigue pendiente"}
        )


@transaction.atomic
def reabrir_recurso(actor, x):
    _guardar_con_auditoria(actor, x, {"estado": "tramite", "resultado": ""}, "reabrir")


@transaction.atomic
def eliminar_recurso(actor, x):
    for a in x.acciones.all():
        _guardar_con_auditoria(actor, a, {"recurso": None})
    x.dar_de_baja(actor.usuario)
    auditar(actor, "eliminar", x, descripcion=x.titulo)


ETIQUETAS_ESTADO = ESTADOS_EXP
