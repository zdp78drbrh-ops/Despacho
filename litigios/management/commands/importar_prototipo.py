"""Importa a Litigios el JSON de "Exportar respaldo" del prototipo (Configuración → Datos).

Los usuarios se relacionan por nombre exacto. Quien no exista se crea inactivo con un correo provisional
(nombre@importado.invalid) para que el administrador lo corrija y le envíe su acceso. Expedientes con el mismo
número y juzgado que uno existente se omiten. Todo queda en la bitácora de auditoría."""

import json
import re
import secrets
import unicodedata
from datetime import date
from decimal import Decimal, InvalidOperation

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from auditoria.servicios import Actor, auditar
from litigios.catalogos import EST_ACC, RECURSOS
from litigios.models import Accion, Acuerdo, Cliente, Documento, EntradaBitacora, Expediente, Recurso


def _fecha(s):
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def _dinero(v):
    try:
        return Decimal(str(v)) if v not in (None, "") else None
    except InvalidOperation:
        return None


def _slug(n):
    n = unicodedata.normalize("NFKD", n).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", ".", n).strip(".") or "usuario"


class Command(BaseCommand):
    help = "Importa expedientes, acciones, recursos, bitácoras, documentos y acuerdos del JSON del prototipo."

    def add_arguments(self, parser):
        parser.add_argument("archivo")
        parser.add_argument("--simular", action="store_true", help="Revisa todo y deshace al final")

    def handle(self, archivo, simular=False, **opts):
        try:
            with open(archivo, encoding="utf-8") as f:
                datos = json.load(f)
        except (OSError, ValueError) as e:
            raise CommandError(f"No se pudo leer el respaldo: {e}") from e
        with transaction.atomic():
            resumen = importar(datos)
            for k, v in resumen.items():
                self.stdout.write(f"{k}: {v}")
            if simular:
                transaction.set_rollback(True)
                self.stdout.write(self.style.WARNING("Simulación: no se guardó nada."))


def importar(datos):
    Usuario = get_user_model()
    actor = Actor()
    cache = {}
    creados = []

    def usuario(nombre):
        nombre = (nombre or "").strip()
        if not nombre or nombre == "Sin asignar":
            return None
        if nombre not in cache:
            u = Usuario.objects.filter(nombre=nombre).first()
            if u is None:
                r = _rol_de(datos, nombre).lower()
                rol = next((k for k in ("aprueba", "revisa", "auxiliar") if k in r), "elabora")
                u = Usuario.objects.create_user(
                    f"{_slug(nombre)}@importado.invalid",
                    nombre,
                    secrets.token_urlsafe(24),
                    rol=rol,
                    is_active=False,
                )
                creados.append(nombre)
                auditar(actor, "importar", u, descripcion=f"Usuario creado inactivo: {nombre}")
            cache[nombre] = u
        return cache[nombre]

    for u in datos.get("usuarios", []):
        usuario(u.get("nombre"))

    mapa_exp, omitidos = {}, 0
    for e in datos.get("expedientes", []):
        if Expediente.objects.filter(numero=e.get("numero", ""), juzgado=e.get("juzgado", "")).exists():
            omitidos += 1
            continue
        razon = " ".join((e.get("cliente") or "Sin cliente").split())
        cliente = Cliente.todos.filter(razon__iexact=razon).first() or Cliente.objects.create(razon=razon)
        exp = Expediente.objects.create(
            numero=e.get("numero", ""),
            anio=str(e.get("anio", ""))[:4],
            juzgado=e.get("juzgado", ""),
            materia=e.get("materia", ""),
            tipo=e.get("tipo", ""),
            cliente=cliente,
            caracter=e.get("caracter") or "Actor",
            contraparte=e.get("contraparte", ""),
            responsable=usuario(e.get("responsable")),
            etapa=e.get("etapa", ""),
            audiencia=_fecha(e.get("audiencia")),
            estado=e.get("estado") if e.get("estado") in ("activo", "sentencia", "terminado") else "activo",
            cuantia=_dinero(e.get("cuantia")),
            esperando_auto=bool(e.get("esperandoAuto")),
        )
        mapa_exp[e.get("id")] = exp
        rec = {}
        for x in e.get("recursos", []) or []:
            tipo = x.get("tipo") if x.get("tipo") in RECURSOS else "Apelación"
            rec[x.get("id")] = Recurso.objects.create(
                expediente=exp,
                tipo=tipo,
                promovente=x.get("promovente") or "Nosotros",
                acto_impugnado=x.get("actoImpugnado", ""),
                numero=x.get("numero", ""),
                organo=x.get("organo", ""),
                fecha_interposicion=_fecha(x.get("fechaInterposicion")),
                etapa=x.get("etapa") or RECURSOS[tipo]["etapas"][0],
                suspension=x.get("suspension") or "No aplica",
                estado="resuelto" if x.get("estado") == "resuelto" else "tramite",
                resultado=x.get("resultado", ""),
                fecha_resolucion=_fecha(x.get("fechaResolucion")),
                notas=x.get("notas", ""),
            )
        for a in e.get("acciones", []) or []:
            Accion.objects.create(
                expediente=exp,
                recurso=rec.get(a.get("recursoId")),
                titulo=a.get("titulo", "")[:250],
                tipo=a.get("tipo") or "Promoción",
                responsable=usuario(a.get("responsable")),
                revisa=usuario(a.get("revisa")),
                aprueba=usuario(a.get("aprueba")),
                plazo=_fecha(a.get("plazo")),
                estado=a.get("estado") if a.get("estado") in EST_ACC else "pendiente",
                notas=a.get("notas", ""),
                acuse=a.get("acuse", ""),
                terminada_el=_fecha(a.get("terminadaEl")),
            )
        for b in e.get("bitacora", []) or []:
            q = usuario(b.get("quien"))
            EntradaBitacora.objects.create(
                expediente=exp,
                fecha=_fecha(b.get("fecha")) or date.today(),
                texto=b.get("texto", ""),
                quien=q,
                quien_nombre=b.get("quien") or "",
            )
        for d in e.get("documentos", []) or []:
            q = usuario(d.get("quien"))
            Documento.objects.create(
                expediente=exp,
                nombre=d.get("nombre", ""),
                fecha=_fecha(d.get("fecha")) or date.today(),
                quien=q,
                quien_nombre=d.get("quien") or "",
            )
        auditar(actor, "importar", exp, descripcion=f"Importado del prototipo: {exp.numero}")

    n_acu = 0
    for a in datos.get("acuerdos", []):
        exp = mapa_exp.get(a.get("expedienteId"))
        if not exp:
            continue
        Acuerdo.objects.create(
            expediente=exp,
            fecha=_fecha(a.get("fecha")) or date.today(),
            sintesis=a.get("sintesis", ""),
            accion=a.get("accion", ""),
            plazo=_fecha(a.get("plazo")),
            registrado_por=usuario(a.get("registradoPor")),
            registrado_por_nombre=a.get("registradoPor") or "",
        )
        n_acu += 1
    return {
        "Expedientes importados": len(mapa_exp),
        "Expedientes omitidos (ya existían)": omitidos,
        "Acuerdos importados": n_acu,
        "Usuarios creados inactivos (corrige su correo y envíales acceso)": ", ".join(creados) or "ninguno",
    }


def _rol_de(datos, nombre):
    return next((u.get("rol", "") for u in datos.get("usuarios", []) if u.get("nombre") == nombre), "")
