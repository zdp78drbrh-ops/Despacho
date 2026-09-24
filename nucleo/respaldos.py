"""Respaldo externo (Backblaze B2 u otro S3): volcado de PostgreSQL, ancla de la cadena de auditoría y réplica de PDF."""

import logging
import os
import subprocess
import tempfile
from datetime import timedelta

import boto3
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import mail_admins, send_mail
from django.utils import timezone

from auditoria.models import EventoAuditoria
from auditoria.servicios import Actor, auditar, verificar_cadena

log = logging.getLogger(__name__)


def _destino():
    c = settings.RESPALDO
    if not c["bucket"]:
        raise RuntimeError("Falta configurar RESPALDO_BUCKET / RESPALDO_ACCESS_KEY / RESPALDO_SECRET_KEY")
    s3 = boto3.client(
        "s3", endpoint_url=c["endpoint_url"], aws_access_key_id=c["access_key"], aws_secret_access_key=c["secret_key"]
    )
    return s3, c["bucket"]


def _url_bd():
    d = settings.DATABASES["default"]
    env = {**os.environ, "PGPASSWORD": d.get("PASSWORD") or ""}
    args = ["-h", d.get("HOST") or "localhost", "-p", str(d.get("PORT") or 5432), "-U", d.get("USER") or "postgres"]
    if d.get("OPTIONS", {}).get("sslmode"):
        env["PGSSLMODE"] = d["OPTIONS"]["sslmode"]
    return args, d["NAME"], env


def volcar_bd(ruta):
    args, nombre, env = _url_bd()
    subprocess.run(["pg_dump", "-Fc", "--no-owner", *args, "-f", ruta, nombre], check=True, env=env)


def respaldar_bd():
    """pg_dump comprimido → bd/AAAA/MM/despacho-AAAAMMDD-HHMM.dump, con cifrado del lado del servidor."""
    s3, bucket = _destino()
    ahora = timezone.localtime()
    clave = f"bd/{ahora:%Y/%m}/despacho-{ahora:%Y%m%d-%H%M}.dump"
    with tempfile.TemporaryDirectory() as tmp:
        ruta = os.path.join(tmp, "despacho.dump")
        volcar_bd(ruta)
        s3.upload_file(ruta, bucket, clave, ExtraArgs={"ServerSideEncryption": "AES256"})
        tamano = os.path.getsize(ruta)
    ultimo = EventoAuditoria.objects.order_by("-id").values("id", "hash").first()
    if ultimo:  # ancla externa: aunque alguien recalculara toda la cadena en la base, no coincidiría con esto
        s3.put_object(
            Bucket=bucket,
            Key=f"anclas/{ahora:%Y%m%d-%H%M}.txt",
            Body=f"{ultimo['id']} {ultimo['hash']}\n".encode(),
            ServerSideEncryption="AES256",
        )
    auditar(Actor(), "respaldo", None, entidad="sistema", descripcion=clave, datos={"bytes": tamano})
    return clave, tamano


def depurar_respaldos(diarios=30, mensuales=12):
    """Conserva los últimos `diarios` días completos y el primer respaldo de cada mes durante `mensuales` meses."""
    s3, bucket = _destino()
    hoy = timezone.localdate()
    limite_diario = hoy - timedelta(days=diarios)
    limite_mensual = hoy - timedelta(days=31 * mensuales)
    objetos = []
    for pag in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="bd/"):
        objetos += pag.get("Contents", [])
    primeros_del_mes = {}
    for o in sorted(objetos, key=lambda o: o["Key"]):
        mes = o["Key"][3:10]
        primeros_del_mes.setdefault(mes, o["Key"])
    borrar = []
    for o in objetos:
        f = timezone.localtime(o["LastModified"]).date()
        if f >= limite_diario:
            continue
        if o["Key"] in primeros_del_mes.values() and f >= limite_mensual:
            continue
        borrar.append(o["Key"])
    for k in borrar:
        s3.delete_object(Bucket=bucket, Key=k)
    return borrar


def replicar_pdf():
    """Copia al respaldo externo los PDF que aún no estén ahí (misma clave)."""
    from django.core.files.storage import default_storage

    from litigios.models import Documento

    s3, bucket = _destino()
    existentes = set()
    for pag in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket, Prefix="pdf/"):
        existentes |= {o["Key"][4:] for o in pag.get("Contents", [])}
    n = 0
    for nombre in Documento.todos.exclude(archivo="").values_list("archivo", flat=True):
        if nombre in existentes:
            continue
        with default_storage.open(nombre, "rb") as f:
            s3.upload_fileobj(f, bucket, f"pdf/{nombre}", ExtraArgs={"ServerSideEncryption": "AES256"})
        n += 1
    return n


def verificar_y_avisar():
    malo = verificar_cadena()
    if malo is not None:
        msg = f"La cadena de la bitácora de auditoría está rota a partir del evento {malo}. Revisar de inmediato."
        log.error(msg)
        destinatarios = list(
            get_user_model().objects.filter(is_staff=True, is_active=True).values_list("email", flat=True)
        )
        if destinatarios:
            send_mail("ALERTA: bitácora de auditoría alterada", msg, None, destinatarios)
        mail_admins("Bitácora de auditoría alterada", msg)
    return malo
