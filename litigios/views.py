"""Pantallas de Litigios. Cada vista corresponde a una ruta del prototipo (#/litigios, #/expediente/:id, …).
Los modales se piden por fetch (static/js/despacho.js); sin JS se muestran como página."""

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.storage import FileSystemStorage
from django.db.models import Prefetch
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from auditoria.servicios import Actor
from nucleo.fechas import dias_hasta, hoy, sumar_dias_habiles

from . import reglas, servicios
from .catalogos import MATERIAS, RECURSOS
from .forms import (
    AccionForm,
    AcuerdoForm,
    AdjuntarForm,
    BitacoraForm,
    DocumentoForm,
    EstadoExpedienteForm,
    EtapaForm,
    ExpedienteForm,
    RecursoForm,
    ResolverForm,
    TerminarForm,
)
from .informes import informe_expediente
from .models import Accion, Acuerdo, Documento, Expediente, Recurso


# ---------- utilidades de vista ----------
def _es_ajax(request):
    return request.headers.get("X-Requested-With") == "fetch"


def _listo(request, url, msg=None):
    if msg:
        messages.success(request, msg)
    if _es_ajax(request):
        r = HttpResponse(status=204)
        r["X-Despacho-Redirect"] = url
        return r
    return redirect(url)


def _modal(request, form, titulo, submit="Guardar", extra="", error="", plantilla="modal_form.html", **ctx):
    ctx.update(
        form=form,
        titulo=titulo,
        submit=submit,
        extra=extra,
        action=request.get_full_path(),
        error=error or (form.texto_errores() if form is not None and form.is_bound else ""),
    )
    if _es_ajax(request):
        return render(request, plantilla, ctx)
    return render(request, "pagina_modal.html", {**ctx, "plantilla": plantilla})


def _actor(request):
    return Actor.de(request)


def _volver(request, defecto):
    ref = request.POST.get("volver") or request.GET.get("volver")
    return ref if ref and ref.startswith("/") and not ref.startswith("//") else defecto


def _expedientes():
    return Expediente.objects.select_related("cliente", "responsable").prefetch_related(
        Prefetch("acciones", queryset=Accion.objects.select_related("responsable")), "bitacora", "recursos"
    )


def _exp_url(e):
    return reverse("expediente", args=[e.pk])


def _tarjeta_expedientes(request, lista):
    materia = request.GET.get("materia", "Todos")
    presentes = {e.materia for e in Expediente.objects.all().only("materia")}
    mats = ["Todos"] + [m for m in MATERIAS if m in presentes]
    return {
        "materias": mats,
        "materia": materia,
        "lista": [e for e in lista if materia == "Todos" or e.materia == materia],
    }


# ---------- tablero ----------
def tablero(request):
    t = hoy()
    todos = list(_expedientes())
    act = [e for e in todos if e.estado == "activo"]
    urg = sorted(((e, e.urgencia()) for e in act if e.urgencia()), key=lambda x: x[1]["orden"])
    esperando = [e for e in act if e.esperando_auto]
    por_actuar = [(e, e.proximo_plazo()) for e in act if not e.esperando_auto and e.pendientes() and not e.urgencia()]
    ids = {e.id for e in todos}
    acuerdos_hoy = [a for a in Acuerdo.objects.filter(fecha=t).select_related("expediente") if a.expediente_id in ids]
    for a in acuerdos_hoy:
        a.chip_cls = (
            "gry" if a.accion == "Solo registrar" else ("amb" if a.plazo and dias_hasta(a.plazo) <= 3 else "blu")
        )
    recursos = [(e, x) for e in todos for x in e.recursos_activos()]
    ctx = {
        "hoy": t,
        "activos": act,
        "urg": urg,
        "esperando": esperando,
        "por_actuar": por_actuar,
        "sent": [e for e in todos if e.estado == "sentencia"],
        "term": [e for e in todos if e.estado == "terminado"],
        "acuerdos_hoy": acuerdos_hoy,
        "recursos": recursos,
        "vacio": not todos,
        **_tarjeta_expedientes(request, act),
    }
    return render(request, "litigios/tablero.html", ctx)


def expedientes(request, filtro=""):
    todos = list(_expedientes())
    titulo, sub = "Expedientes", ""
    if filtro == "urgentes":
        lista, titulo = [e for e in todos if e.estado == "activo" and e.urgencia()], "Por vencer o sin impulso"
    elif filtro == "sentencia":
        lista, titulo = [e for e in todos if e.estado == "sentencia"], "En espera de sentencia"
    elif filtro == "terminados":
        lista, titulo = [e for e in todos if e.estado == "terminado"], "Expedientes terminados"
    elif filtro:
        raise Http404
    else:
        lista, sub = todos, f"{len(todos)} en total"
    return render(
        request, "litigios/expedientes.html", {"titulo": titulo, "sub": sub, **_tarjeta_expedientes(request, lista)}
    )


# ---------- ficha ----------
def expediente(request, pk):
    e = get_object_or_404(_expedientes(), pk=pk)
    acciones = sorted(
        Accion.objects.filter(expediente=e).select_related("responsable", "revisa", "aprueba", "recurso"),
        key=lambda a: (a.estado == "terminada", a.plazo.isoformat() if a.plazo else "9"),
    )
    u = request.user
    for a in acciones:
        a.btn = a.boton()
        a.confirmar = ""
        if a.btn and a.btn[1] == "Aprobar":
            a.puede = reglas.puede_aprobar(u, a.aprueba_id, a.revisa_id)
            if a.aprueba_id and a.aprueba_id != u.pk:
                a.confirmar = f"Esta acción la aprueba {a.aprueba.nombre}. ¿Aprobar de todos modos como {u.nombre}?"
        else:
            a.puede = True
    recursos = list(e.recursos.all())
    for x in recursos:
        x.pendientes = [a for a in acciones if a.recurso_id == x.id and a.estado != "terminada"]
    ctx = {
        "e": e,
        "u": e.ultima(),
        "urg": e.urgencia(),
        "acciones": acciones,
        "recursos": recursos,
        "bitacora": e.bitacora.all(),
        "documentos": e.documentos.select_related("quien"),
        "acuerdos": e.acuerdos.all(),
    }
    return render(request, "litigios/expediente.html", ctx)


def expediente_nuevo(request):
    form = ExpedienteForm(request.POST or None, usuario=request.user)
    if request.method == "POST" and form.is_valid():
        e = servicios.crear_expediente(_actor(request), form.cleaned_data)
        return _listo(request, _exp_url(e), "Expediente creado")
    return _modal(request, form, "Nuevo expediente", clientes=form.clientes)


def expediente_editar(request, pk):
    e = get_object_or_404(Expediente, pk=pk)
    form = ExpedienteForm(request.POST or None, instancia=e)
    if request.method == "POST" and form.is_valid():
        servicios.editar_expediente(_actor(request), e, form.cleaned_data)
        return _listo(request, _exp_url(e))
    extra = ""
    if request.user.puede_aprobar:
        extra = {
            "url": reverse("expediente_eliminar", args=[e.pk]),
            "confirmar": f"¿Eliminar el expediente {e.numero}? Esta acción no se puede deshacer.",
        }
    return _modal(request, form, "Editar expediente", extra=extra, clientes=form.clientes)


@require_POST
def expediente_eliminar(request, pk):
    e = get_object_or_404(Expediente, pk=pk)
    servicios.eliminar_expediente(_actor(request), e)
    return _listo(request, reverse("expedientes"), "Expediente eliminado")


def expediente_etapa(request, pk):
    e = get_object_or_404(Expediente, pk=pk)
    form = EtapaForm(request.POST or None, initial={"etapa": e.etapa})
    if request.method == "POST" and form.is_valid():
        servicios.cambiar_etapa(_actor(request), e, form.cleaned_data["etapa"])
        return _listo(request, _exp_url(e))
    return _modal(request, form, "Cambiar etapa procesal")


def expediente_estado(request, pk):
    e = get_object_or_404(Expediente, pk=pk)
    form = EstadoExpedienteForm(request.POST or None, initial={"estado": e.estado})
    if request.method == "POST" and form.is_valid():
        servicios.cambiar_estado_expediente(_actor(request), e, form.cleaned_data["estado"], form.cleaned_data["nota"])
        return _listo(request, _exp_url(e))
    return _modal(request, form, "Estado del expediente")


def expediente_informe(request, pk):
    e = get_object_or_404(_expedientes(), pk=pk)
    return _modal(
        request,
        None,
        "Informe al cliente",
        plantilla="modal_texto.html",
        texto=informe_expediente(e, request.user.nombre),
        pista="Texto listo para pegar en un correo. Ajusta lo que haga falta antes de enviarlo.",
    )


# ---------- acciones ----------
def accion_nueva(request, pk):
    e = get_object_or_404(Expediente, pk=pk)
    initial = {}
    if request.GET.get("recurso"):
        initial["recurso"] = request.GET["recurso"]
    form = AccionForm(request.POST or None, expediente=e, usuario=request.user, initial=initial)
    if request.method == "POST" and form.is_valid():
        servicios.crear_accion(_actor(request), e, form.cleaned_data)
        return _listo(request, _exp_url(e), "Acción agregada")
    return _modal(request, form, "Nueva acción")


def accion_editar(request, pk):
    a = get_object_or_404(Accion.objects.select_related("expediente"), pk=pk)
    estados = servicios.estados_permitidos_en_edicion(_actor(request), a)
    campos = ["recurso", "titulo", "tipo", "plazo", "responsable", "revisa", "aprueba", "notas", "estado"]
    form = AccionForm(
        request.POST or None, expediente=a.expediente, estados=estados, initial={k: getattr(a, k) for k in campos}
    )
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            servicios.editar_accion(_actor(request), a, form.cleaned_data)
            return _listo(request, _exp_url(a.expediente))
        except PermissionDenied as ex:
            error = str(ex)
    extra = {"url": reverse("accion_eliminar", args=[a.pk]), "confirmar": "¿Eliminar esta acción?"}
    return _modal(request, form, "Editar acción", extra=extra, error=error)


@require_POST
def accion_eliminar(request, pk):
    a = get_object_or_404(Accion, pk=pk)
    servicios.eliminar_accion(_actor(request), a)
    return _listo(request, _exp_url(a.expediente))


@require_POST
def accion_avanzar(request, pk):
    a = get_object_or_404(Accion.objects.select_related("expediente", "aprueba"), pk=pk)
    try:
        servicios.avanzar_accion(_actor(request), a, confirmado=request.POST.get("confirmado") == "1")
    except PermissionDenied as ex:
        messages.error(request, str(ex))
    return _listo(request, _exp_url(a.expediente))


def accion_terminar(request, pk):
    a = get_object_or_404(Accion.objects.select_related("expediente"), pk=pk)
    form = TerminarForm(
        request.POST or None,
        request.FILES or None,
        initial={"fecha": hoy(), "doc": reglas.espera_auto_al_terminar(a.tipo)},
    )
    error = ""
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            servicios.terminar_accion(_actor(request), a, d["fecha"], d["acuse"], d["doc"], d.get("archivo"))
            return _listo(request, _exp_url(a.expediente), "Acción terminada")
        except (PermissionDenied, ValidationError) as ex:
            error = " ".join(getattr(ex, "messages", [str(ex)]))
    return _modal(request, form, "Marcar como terminada", submit="Terminar", error=error, multipart=True)


# ---------- acuerdos ----------
def acuerdos(request):
    lista = list(
        Acuerdo.objects.select_related("expediente", "expediente__cliente").filter(
            expediente__eliminado_en__isnull=True
        )
    )
    dias = []
    for a in lista:
        if not dias or dias[-1][0] != a.fecha:
            dias.append((a.fecha, []))
        dias[-1][1].append(a)
    return render(request, "litigios/acuerdos.html", {"dias": dias})


def acuerdo_nuevo(request):
    if not Expediente.objects.exclude(estado="terminado").exists():
        messages.info(request, "Primero da de alta un expediente")
        return _listo(request, reverse("tablero"))
    form = AcuerdoForm(request.POST or None, initial={"expediente": request.GET.get("expediente"), "fecha": hoy()})
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        servicios.registrar_acuerdo(
            _actor(request), d["expediente"], d["fecha"], d["sintesis"], d["accion"], d["plazo"], d["crear"]
        )
        return _listo(request, _volver(request, reverse("tablero")), "Acuerdo registrado")
    return _modal(request, form, "Registrar acuerdo publicado")


# ---------- documentos y bitácora ----------
def documento_nuevo(request, pk):
    e = get_object_or_404(Expediente, pk=pk)
    form = DocumentoForm(request.POST or None, request.FILES or None, initial={"fecha": hoy()})
    error = ""
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        try:
            servicios.agregar_documento(_actor(request), e, d["nombre"], d["fecha"], d.get("archivo"))
            return _listo(request, _exp_url(e), "Documento registrado")
        except ValidationError as ex:
            error = " ".join(ex.messages)
    return _modal(request, form, "Registrar documento del expediente", error=error, multipart=True)


def documento_adjuntar(request, pk):
    doc = get_object_or_404(Documento.objects.select_related("expediente"), pk=pk)
    form = AdjuntarForm(request.POST or None, request.FILES or None)
    error = ""
    if request.method == "POST" and form.is_valid():
        try:
            servicios.adjuntar_pdf(_actor(request), doc, form.cleaned_data["archivo"])
            return _listo(request, _exp_url(doc.expediente), "PDF adjuntado")
        except ValidationError as ex:
            error = " ".join(ex.messages)
    return _modal(request, form, f"Adjuntar PDF · {doc.nombre}", submit="Subir", error=error, multipart=True)


def documento_descargar(request, pk):
    doc = get_object_or_404(Documento, pk=pk)
    if not doc.archivo:
        raise Http404
    servicios.registrar_descarga(_actor(request), doc)
    nombre = f"{doc.nombre}.pdf".replace('"', "")
    if isinstance(doc.archivo.storage, FileSystemStorage):
        return FileResponse(doc.archivo.open("rb"), content_type="application/pdf", filename=nombre)
    url = doc.archivo.storage.url(
        doc.archivo.name,
        parameters={
            "ResponseContentDisposition": f'inline; filename="{nombre}"',
            "ResponseContentType": "application/pdf",
        },
    )
    return redirect(url)


@require_POST
def documento_quitar(request, pk):
    doc = get_object_or_404(Documento, pk=pk)
    servicios.quitar_documento(_actor(request), doc)
    return _listo(request, _exp_url(doc.expediente))


def bitacora_nueva(request, pk):
    e = get_object_or_404(Expediente, pk=pk)
    form = BitacoraForm(request.POST or None, initial={"fecha": hoy()})
    if request.method == "POST" and form.is_valid():
        servicios.anotar_bitacora(_actor(request), e, form.cleaned_data["texto"], form.cleaned_data["fecha"])
        return _listo(request, _exp_url(e))
    return _modal(request, form, "Anotar en la bitácora")


# ---------- recursos ----------
def recursos(request):
    todos = [
        (x.expediente, x)
        for x in Recurso.objects.select_related("expediente", "expediente__cliente")
        .prefetch_related("acciones")
        .filter(expediente__eliminado_en__isnull=True)
    ]
    tram = [(e, x) for e, x in todos if x.estado != "resuelto"]
    tipos = []
    for _, x in tram:
        if x.tipo not in tipos:
            tipos.append(x.tipo)
    grupos = [(t, [(e, x) for e, x in tram if x.tipo == t]) for t in tipos]
    return render(
        request,
        "litigios/recursos.html",
        {
            "tram": tram,
            "grupos": grupos,
            "resueltos": [(e, x) for e, x in todos if x.estado == "resuelto"],
            "catalogo": RECURSOS,
        },
    )


def recurso_nuevo(request, pk=None):
    e = get_object_or_404(Expediente, pk=pk) if pk else None
    if e is None and not Expediente.objects.exists():
        messages.info(request, "Primero da de alta un expediente")
        return _listo(request, reverse("recursos"))
    tipo = request.GET.get("tipo") or "Apelación"
    form = RecursoForm(
        request.POST or None,
        con_expediente=e is None,
        initial={"tipo": tipo, "etapa": RECURSOS.get(tipo, RECURSOS["Apelación"])["etapas"][0]},
    )
    if request.method == "POST" and form.is_valid():
        d = dict(form.cleaned_data)
        exp = d.pop("expediente", None) or e
        servicios.crear_recurso(_actor(request), exp, d)
        return _listo(request, _exp_url(exp), "Recurso registrado")
    titulo = f"Nueva {request.GET['tipo'].lower()}" if request.GET.get("tipo") else "Nuevo recurso"
    return _modal(request, form, titulo, recursos_json=RECURSOS)


def recurso_editar(request, pk):
    x = get_object_or_404(Recurso.objects.select_related("expediente"), pk=pk)
    campos = [
        "tipo",
        "promovente",
        "acto_impugnado",
        "numero",
        "organo",
        "fecha_interposicion",
        "etapa",
        "suspension",
        "notas",
    ]
    form = RecursoForm(request.POST or None, initial={k: getattr(x, k) for k in campos})
    if request.method == "POST" and form.is_valid():
        servicios.editar_recurso(_actor(request), x, form.cleaned_data)
        return _listo(request, _exp_url(x.expediente))
    extra = {
        "url": reverse("recurso_eliminar", args=[x.pk]),
        "confirmar": "¿Eliminar este recurso? Sus acciones quedan en el expediente.",
    }
    return _modal(request, form, "Editar recurso", extra=extra, recursos_json=RECURSOS)


@require_POST
def recurso_etapa(request, pk, direccion):
    x = get_object_or_404(Recurso.objects.select_related("expediente"), pk=pk)
    servicios.mover_etapa_recurso(_actor(request), x, 1 if direccion == "avanzar" else -1)
    return _listo(request, _exp_url(x.expediente))


def recurso_resolver(request, pk):
    x = get_object_or_404(Recurso.objects.select_related("expediente"), pk=pk)
    form = ResolverForm(
        request.POST or None,
        initial={"resultado": x.resultado or "Favorable", "fecha": hoy(), "etapa_exp": x.expediente.etapa},
    )
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        servicios.resolver_recurso(_actor(request), x, d["resultado"], d["fecha"], d["sintesis"], d["etapa_exp"])
        return _listo(request, _exp_url(x.expediente), "Recurso resuelto")
    return _modal(request, form, "Resolver recurso", submit="Registrar resolución")


@require_POST
def recurso_reabrir(request, pk):
    x = get_object_or_404(Recurso.objects.select_related("expediente"), pk=pk)
    servicios.reabrir_recurso(_actor(request), x)
    return _listo(request, _exp_url(x.expediente))


@require_POST
def recurso_eliminar(request, pk):
    x = get_object_or_404(Recurso.objects.select_related("expediente"), pk=pk)
    servicios.eliminar_recurso(_actor(request), x)
    return _listo(request, _exp_url(x.expediente))


# ---------- calendario y equipo (fase 1: solo litigios) ----------
def calendario(request):
    t = hoy()
    ev = []
    for e in _expedientes().exclude(estado="terminado"):
        url = _exp_url(e)
        if e.audiencia:
            ev.append(
                {
                    "fecha": e.audiencia,
                    "tipo": "Audiencia",
                    "txt": f"{e.numero} · {e.cliente.razon}",
                    "go": url,
                    "cls": "blu",
                }
            )
        for a in e.pendientes():
            if a.plazo:
                resp = a.responsable.nombre if a.responsable else ""
                ev.append(
                    {
                        "fecha": a.plazo,
                        "tipo": "Plazo",
                        "txt": f"{a.titulo} · {e.numero} · {resp}",
                        "go": url,
                        "cls": "amb",
                    }
                )
    ev.sort(key=lambda x: x["fecha"])
    venc = [x for x in ev if x["fecha"] < t]
    prox = [x for x in ev if x["fecha"] >= t and (x["fecha"] - t).days <= 120]
    dias = []
    for x in prox:
        if not dias or dias[-1]["fecha"] != x["fecha"]:
            n = (x["fecha"] - t).days
            dias.append({"fecha": x["fecha"], "n": n, "items": []})
        dias[-1]["items"].append(x)
    mitad = (len(dias) + 1) // 2
    return render(
        request, "litigios/calendario.html", {"venc": venc, "col1": dias[:mitad], "col2": dias[mitad:], "vacio": not ev}
    )


def equipo(request):
    from django.contrib.auth import get_user_model

    usuarios = list(get_user_model().objects.filter(is_active=True))
    acciones = [a for e in _expedientes().exclude(estado="terminado") for a in e.pendientes()]
    tarjetas = []
    for u in usuarios:
        items = []
        for a in acciones:
            rol = reglas.rol_en_tarea(a.estado, u.pk, a.responsable_id, a.revisa_id, a.aprueba_id)
            if rol:
                e = a.expediente
                items.append(
                    {
                        "txt": f"{a.titulo} · {e.numero}",
                        "sub": None,
                        "plazo": a.plazo,
                        "go": _exp_url(e),
                        "chip": rol,
                        "cls": reglas.clase_por_plazo(a.plazo) if a.plazo else "blu",
                        "o": a.plazo.isoformat() if a.plazo else "9",
                    }
                )
        items.sort(key=lambda i: i["o"])
        tarjetas.append({"u": u, "items": items})
    return render(request, "litigios/equipo.html", {"col1": tarjetas[0::2], "col2": tarjetas[1::2]})


def calcular_plazo(request):
    """Días hábiles desde una fecha (hoy por defecto). Fase 2: sumará los días inhábiles del calendario."""
    try:
        n = int(request.GET.get("dias", "0"))
        desde = request.GET.get("desde")
        from datetime import date

        base = date.fromisoformat(desde) if desde else hoy()
    except ValueError:
        return JsonResponse({"error": "Dato inválido"}, status=400)
    if n <= 0 or n > 365:
        return JsonResponse({"error": "Indica un número de días entre 1 y 365"}, status=400)
    return JsonResponse({"fecha": sumar_dias_habiles(base, n).isoformat()})


def corporativo(request):
    return render(request, "litigios/proximamente.html", {"titulo": "Servicios corporativos", "fase": 3})
