import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from nucleo.fechas import dias_desde

from . import reglas
from .catalogos import EST_ACC, ESTADOS_EXP, RECURSOS

U = settings.AUTH_USER_MODEL


class VivosManager(models.Manager):
    """Oculta lo dado de baja. Nada se borra físicamente."""

    def get_queryset(self):
        return super().get_queryset().filter(eliminado_en__isnull=True)


class ConBaja(models.Model):
    eliminado_en = models.DateTimeField(null=True, blank=True, editable=False)
    eliminado_por = models.ForeignKey(
        U, null=True, blank=True, on_delete=models.PROTECT, related_name="+", editable=False
    )
    objects = VivosManager()
    todos = models.Manager()

    class Meta:
        abstract = True
        base_manager_name = "todos"

    def dar_de_baja(self, usuario):
        self.eliminado_en = timezone.now()
        self.eliminado_por = usuario
        self.save(update_fields=["eliminado_en", "eliminado_por"])


class Cliente(ConBaja):
    """Mínimo para la fase 1 (agrupar expedientes y PDF). Se completa en la fase 3 (servicios corporativos)."""

    razon = models.CharField("razón social o nombre", max_length=200, unique=True)
    rfc = models.CharField("RFC", max_length=13, blank=True)
    representante = models.CharField("representante legal", max_length=150, blank=True)
    contacto = models.CharField("contacto", max_length=200, blank=True)
    responsable = models.ForeignKey(U, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["razon"]

    def __str__(self):
        return self.razon


class Expediente(ConBaja):
    numero = models.CharField("número de expediente", max_length=60)
    anio = models.CharField("año", max_length=4)
    juzgado = models.CharField("juzgado", max_length=200)
    materia = models.CharField("materia", max_length=30)
    tipo = models.CharField("tipo de asunto", max_length=120, blank=True)
    cliente = models.ForeignKey(Cliente, on_delete=models.PROTECT, related_name="expedientes")
    caracter = models.CharField("carácter del cliente", max_length=40, default="Actor")
    contraparte = models.CharField("contraparte", max_length=200, blank=True)
    responsable = models.ForeignKey(
        U, null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="abogado responsable"
    )
    etapa = models.CharField("etapa procesal", max_length=60)
    audiencia = models.DateField("próxima audiencia", null=True, blank=True)
    estado = models.CharField(max_length=12, choices=list(ESTADOS_EXP.items()), default="activo")
    cuantia = models.DecimalField("cuantía (MXN)", max_digits=16, decimal_places=2, null=True, blank=True)
    esperando_auto = models.BooleanField(default=False)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creado_en", "id"]

    def __str__(self):
        return self.titulo

    @property
    def titulo(self):
        return f"{self.numero} · {self.tipo or self.materia}"

    # --- derivados (mismos nombres que el prototipo) ---
    def acciones_vivas(self):
        cache = getattr(self, "_prefetched_objects_cache", {})
        return list(cache["acciones"]) if "acciones" in cache else list(self.acciones.all())

    def pendientes(self):
        return [a for a in self.acciones_vivas() if a.estado != "terminada"]

    def proximo_plazo(self):
        p = sorted((a for a in self.pendientes() if a.plazo), key=lambda a: a.plazo)
        return p[0] if p else None

    def ultima(self):
        cache = getattr(self, "_prefetched_objects_cache", {})
        b = list(cache["bitacora"]) if "bitacora" in cache else list(self.bitacora.all())
        return max(b, key=lambda x: (x.fecha, x.id)) if b else None

    def dias_sin(self):
        u = self.ultima()
        return dias_desde(u.fecha) if u else None

    def urgencia(self):
        p = self.proximo_plazo()
        return reglas.urgencia(p.plazo if p else None, self.dias_sin())

    def recursos_vivos(self):
        cache = getattr(self, "_prefetched_objects_cache", {})
        return list(cache["recursos"]) if "recursos" in cache else list(self.recursos.all())

    def recursos_activos(self):
        return [r for r in self.recursos_vivos() if r.estado != "resuelto"]

    def chip_estado(self):
        return {"terminado": ("grn", "Terminado"), "sentencia": ("gry", "Sentencia")}.get(
            self.estado, ("blu", "Activo")
        )


class Recurso(ConBaja):
    expediente = models.ForeignKey(Expediente, on_delete=models.PROTECT, related_name="recursos")
    tipo = models.CharField("tipo de recurso", max_length=40)
    promovente = models.CharField("quién lo promueve", max_length=20, default="Nosotros")
    acto_impugnado = models.CharField("acto o resolución impugnada", max_length=300, blank=True)
    numero = models.CharField("toca o número de expediente", max_length=60, blank=True)
    organo = models.CharField("órgano que lo resuelve", max_length=200, blank=True)
    fecha_interposicion = models.DateField("fecha de interposición", null=True, blank=True)
    etapa = models.CharField("etapa actual", max_length=80)
    suspension = models.CharField("suspensión", max_length=40, default="No aplica")
    estado = models.CharField(max_length=10, default="tramite")  # tramite | resuelto
    resultado = models.CharField(max_length=40, blank=True)
    fecha_resolucion = models.DateField(null=True, blank=True)
    notas = models.TextField(blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creado_en", "id"]

    def __str__(self):
        return self.titulo

    @property
    def titulo(self):
        return f"{self.tipo}{' · ' + self.numero if self.numero else ''}"

    @property
    def etapas(self):
        return RECURSOS.get(self.tipo, {}).get("etapas", [])

    @property
    def etapa_idx(self):
        return self.etapas.index(self.etapa) if self.etapa in self.etapas else -1

    @property
    def avance_pct(self):
        return round((self.etapa_idx + 1) / max(len(self.etapas), 1) * 100)

    @property
    def siguiente_etapa(self):
        i = self.etapa_idx
        return self.etapas[i + 1] if i + 1 < len(self.etapas) else None

    def chip(self):
        return reglas.chip_recurso(self.estado, self.resultado, self.promovente)

    def chip_suspension(self):
        return reglas.chip_suspension(self.tipo, self.suspension)


class Accion(ConBaja):
    expediente = models.ForeignKey(Expediente, on_delete=models.PROTECT, related_name="acciones")
    recurso = models.ForeignKey(Recurso, null=True, blank=True, on_delete=models.SET_NULL, related_name="acciones")
    titulo = models.CharField("documento, promoción o acto", max_length=250)
    tipo = models.CharField(max_length=30, default="Promoción")
    responsable = models.ForeignKey(
        U, null=True, blank=True, on_delete=models.PROTECT, related_name="+", verbose_name="responsable (elabora)"
    )
    revisa = models.ForeignKey(U, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    aprueba = models.ForeignKey(U, null=True, blank=True, on_delete=models.PROTECT, related_name="+")
    plazo = models.DateField("fecha límite o plazo judicial", null=True, blank=True)
    estado = models.CharField(max_length=12, choices=[(k, v[0]) for k, v in EST_ACC.items()], default="pendiente")
    notas = models.TextField(blank=True)
    acuse = models.CharField(max_length=200, blank=True)
    terminada_el = models.DateField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["creado_en", "id"]

    def __str__(self):
        return self.titulo

    @property
    def terminada(self):
        return self.estado == "terminada"

    def chip_estado(self):
        lab, cls = EST_ACC.get(self.estado, EST_ACC["pendiente"])
        return cls, lab

    def boton(self):
        return reglas.boton_accion(self.estado, bool(self.revisa_id), bool(self.aprueba_id))

    def estilo_plazo(self):
        return reglas.estilo_plazo(self.plazo, self.terminada)


class Acuerdo(models.Model):
    """Acuerdo publicado en la lista del juzgado. Solo alta (como en el prototipo)."""

    expediente = models.ForeignKey(Expediente, on_delete=models.PROTECT, related_name="acuerdos")
    fecha = models.DateField("fecha de publicación")
    sintesis = models.TextField("qué se acordó")
    accion = models.CharField("acción a seguir", max_length=250, blank=True)
    plazo = models.DateField("plazo que corre", null=True, blank=True)
    registrado_por = models.ForeignKey(U, null=True, on_delete=models.PROTECT, related_name="+")
    registrado_por_nombre = models.CharField(max_length=120, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.fecha} · {self.sintesis[:60]}"


class EntradaBitacora(models.Model):
    """Bitácora visible del expediente. Solo alta: la base rechaza UPDATE/DELETE (migración 0002)."""

    expediente = models.ForeignKey(Expediente, on_delete=models.PROTECT, related_name="bitacora")
    fecha = models.DateField()
    texto = models.TextField()
    quien = models.ForeignKey(U, null=True, on_delete=models.PROTECT, related_name="+")
    quien_nombre = models.CharField(max_length=120)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-fecha", "-id"]

    def __str__(self):
        return f"{self.fecha} · {self.texto[:60]}"


def ruta_pdf(instancia, _nombre):
    e = instancia.expediente
    return f"clientes/{e.cliente_id}/expedientes/{e.id}/{uuid.uuid4().hex}.pdf"


class Documento(ConBaja):
    """Constancia del expediente digitalizado. El PDF es opcional (los registros importados del prototipo no lo tienen)."""

    expediente = models.ForeignKey(Expediente, on_delete=models.PROTECT, related_name="documentos")
    nombre = models.CharField("nombre de la constancia", max_length=250)
    fecha = models.DateField()
    quien = models.ForeignKey(U, null=True, on_delete=models.PROTECT, related_name="+")
    quien_nombre = models.CharField(max_length=120, blank=True)
    archivo = models.FileField(upload_to=ruta_pdf, max_length=300, blank=True)
    sha256 = models.CharField(max_length=64, blank=True)
    tamano = models.PositiveBigIntegerField(null=True, blank=True)
    creado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["fecha", "id"]

    def __str__(self):
        return self.nombre


class NotificacionEnviada(models.Model):
    """Evita repetir correos (fase 2). Se crea desde ya para no migrar después."""

    accion = models.ForeignKey(Accion, on_delete=models.PROTECT, related_name="notificaciones")
    tipo = models.CharField(max_length=20)  # rojo
    plazo = models.DateField(null=True)
    enviada_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["accion", "tipo", "plazo"], name="notificacion_unica")]

    def __str__(self):
        return f"{self.tipo} · {self.accion_id}"
