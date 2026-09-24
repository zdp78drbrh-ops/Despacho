"""Formularios con el mismo orden, etiquetas y agrupación en dos columnas ('half') que formModal() del prototipo."""

from django import forms
from django.contrib.auth import get_user_model

from nucleo.fechas import hoy

from .catalogos import (
    CARACTERES,
    EST_ACC,
    ETAPAS,
    MATERIAS,
    PROMOVENTES,
    RECURSOS,
    RESULTADOS,
    SUSPENSION,
    TIPOS_ACCION,
)
from .models import Cliente, Expediente, Recurso


def _opciones(lista):
    return [(x, x) for x in lista]


class FechaInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kw):
        super().__init__(format="%Y-%m-%d", **kw)


class UsuarioChoice(forms.ModelChoiceField):
    def __init__(self, **kw):
        super().__init__(
            queryset=get_user_model().objects.filter(is_active=True),
            required=False,
            empty_label="— Sin asignar —",
            **kw,
        )

    def label_from_instance(self, u):
        return u.nombre


class FormDespacho(forms.Form):
    """`mitades`: campos que van de dos en dos (f2). `pistas`: HTML de ayuda bajo el campo."""

    mitades: set = set()
    pistas: dict = {}
    placeholders: dict = {}

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        for k, p in self.placeholders.items():
            if k in self.fields:
                self.fields[k].widget.attrs["placeholder"] = p

    def filas(self):
        campos = [self[n] for n in self.fields]
        filas, i = [], 0
        while i < len(campos):
            f = campos[i]
            if f.name in self.mitades and i + 1 < len(campos) and campos[i + 1].name in self.mitades:
                filas.append([f, campos[i + 1]])
                i += 2
            else:
                filas.append([f])
                i += 1
        return filas

    def pista(self, nombre):
        return self.pistas.get(nombre, "")

    def texto_errores(self):
        faltan = [
            self.fields[k].label
            for k, errs in self.errors.items()
            if k != "__all__" and any(e.code == "required" for e in errs.as_data())
        ]
        otros = [
            str(m)
            for k, errs in self.errors.items()
            for e in errs.as_data()
            if e.code != "required"
            for m in e.messages
        ]
        partes = (["Falta: " + ", ".join(faltan)] if faltan else []) + otros
        return " · ".join(partes)


PISTA_PLAZO = '<span class="lnk" data-calc-plazo>Calcular a partir de días hábiles</span>'


class ExpedienteForm(FormDespacho):
    mitades = {
        "numero",
        "anio",
        "materia",
        "tipo",
        "cliente_nombre",
        "caracter",
        "responsable",
        "etapa",
        "audiencia",
        "cuantia",
    }
    placeholders = {"numero": "312/2025", "juzgado": "Juzgado 2° Civil, Querétaro", "tipo": "Oral mercantil"}

    numero = forms.CharField(label="Número de expediente", max_length=60)
    anio = forms.CharField(label="Año", max_length=4)
    juzgado = forms.CharField(label="Juzgado", max_length=200)
    materia = forms.ChoiceField(label="Materia", choices=_opciones(MATERIAS), initial="Mercantil")
    tipo = forms.CharField(label="Tipo de asunto", max_length=120, required=False)
    cliente_nombre = forms.CharField(
        label="Cliente", max_length=200, widget=forms.TextInput(attrs={"list": "lista-clientes", "autocomplete": "off"})
    )
    caracter = forms.ChoiceField(label="Carácter del cliente", choices=_opciones(CARACTERES), initial="Actor")
    contraparte = forms.CharField(label="Contraparte", max_length=200, required=False)
    responsable = UsuarioChoice(label="Abogado responsable")
    etapa = forms.ChoiceField(label="Etapa procesal", choices=_opciones(ETAPAS), initial=ETAPAS[0])
    audiencia = forms.DateField(label="Próxima audiencia", required=False, widget=FechaInput())
    cuantia = forms.DecimalField(label="Cuantía (MXN)", required=False, max_digits=16, decimal_places=2)

    def __init__(self, *a, usuario=None, instancia: Expediente | None = None, **kw):
        if instancia is not None and "initial" not in kw:
            kw["initial"] = {f: getattr(instancia, f) for f in self.base_fields if f != "cliente_nombre"}
            kw["initial"]["cliente_nombre"] = instancia.cliente.razon
        super().__init__(*a, **kw)
        if instancia is None:
            self.fields["anio"].initial = str(hoy().year)
            self.fields["responsable"].initial = usuario
        self.clientes = Cliente.objects.values_list("razon", flat=True)


class EtapaForm(FormDespacho):
    etapa = forms.ChoiceField(label="Etapa", choices=_opciones(ETAPAS))


class EstadoExpedienteForm(FormDespacho):
    estado = forms.ChoiceField(
        label="Estado",
        choices=[("activo", "Activo"), ("sentencia", "En espera de sentencia"), ("terminado", "Terminado")],
    )
    nota = forms.CharField(
        label="Nota (opcional)",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Sentencia favorable, convenio, desistimiento…"}),
    )


class AccionForm(FormDespacho):
    mitades = {"tipo", "plazo", "responsable", "revisa"}
    pistas = {"plazo": PISTA_PLAZO}
    placeholders = {"titulo": "Escrito de designación de perito"}

    recurso = forms.ModelChoiceField(
        label="Pertenece a",
        queryset=Recurso.objects.none(),
        required=False,
        empty_label="Expediente principal (primera instancia)",
    )
    titulo = forms.CharField(label="Documento, promoción o acto", max_length=250)
    tipo = forms.ChoiceField(label="Tipo", choices=_opciones(TIPOS_ACCION), initial="Promoción")
    plazo = forms.DateField(label="Fecha límite o plazo judicial", required=False, widget=FechaInput())
    responsable = UsuarioChoice(label="Responsable (elabora)")
    revisa = UsuarioChoice(label="Revisa")
    aprueba = UsuarioChoice(label="Aprueba")
    notas = forms.CharField(label="Notas", required=False, widget=forms.Textarea)
    estado = forms.ChoiceField(label="Estado", choices=[(k, v[0]) for k, v in EST_ACC.items()], required=False)

    def __init__(self, *a, expediente, estados=None, usuario=None, **kw):
        super().__init__(*a, **kw)
        recursos = expediente.recursos.all()
        if recursos.exists():
            self.fields["recurso"].queryset = recursos
            self.fields["recurso"].label_from_instance = lambda x: x.titulo
        else:
            del self.fields["recurso"]
        if estados is None:
            del self.fields["estado"]
        else:
            self.fields["estado"].choices = [(k, EST_ACC[k][0]) for k in estados]
        if "responsable" not in self.initial:
            self.fields["responsable"].initial = usuario

    def clean_estado(self):
        return self.cleaned_data.get("estado") or self.initial.get("estado")


class TerminarForm(FormDespacho):
    acuse = forms.CharField(
        label="Acuse, folio o referencia",
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Acuse de recibo 23 sep, oficialía de partes"}),
    )
    fecha = forms.DateField(label="Fecha en que se realizó", widget=FechaInput())
    doc = forms.BooleanField(label="Registrar también como documento del expediente", required=False)
    archivo = forms.FileField(
        label="PDF del acuse (opcional)",
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}),
    )


class AcuerdoForm(FormDespacho):
    mitades = {"fecha", "plazo"}
    pistas = {"plazo": PISTA_PLAZO}
    placeholders = {"accion": "Designar perito · Desahogar vista · Solo registrar"}

    expediente = forms.ModelChoiceField(
        label="Expediente", queryset=Expediente.objects.exclude(estado="terminado"), empty_label=None
    )
    fecha = forms.DateField(label="Fecha de publicación", widget=FechaInput())
    plazo = forms.DateField(label="Plazo que corre (si aplica)", required=False, widget=FechaInput())
    sintesis = forms.CharField(label="Qué se acordó", widget=forms.Textarea)
    accion = forms.CharField(label="Acción a seguir", required=False, max_length=250)
    crear = forms.BooleanField(label="Crear la acción en el expediente con este plazo", required=False, initial=True)

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["expediente"].label_from_instance = lambda e: f"{e.numero} · {e.cliente.razon}"
        self.fields["expediente"].queryset = Expediente.objects.exclude(estado="terminado").select_related("cliente")


class DocumentoForm(FormDespacho):
    nombre = forms.CharField(
        label="Nombre de la constancia",
        max_length=250,
        widget=forms.TextInput(attrs={"placeholder": "06 Auto que admite pruebas"}),
    )
    fecha = forms.DateField(label="Fecha", widget=FechaInput())
    archivo = forms.FileField(
        label="Archivo PDF", required=False, widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"})
    )


class AdjuntarForm(FormDespacho):
    archivo = forms.FileField(label="Archivo PDF", widget=forms.ClearableFileInput(attrs={"accept": "application/pdf"}))


class BitacoraForm(FormDespacho):
    texto = forms.CharField(label="Qué pasó", widget=forms.Textarea)
    fecha = forms.DateField(label="Fecha", widget=FechaInput())


class RecursoForm(FormDespacho):
    mitades = {"tipo", "promovente", "numero", "organo", "fecha_interposicion", "etapa"}
    placeholders = {"acto_impugnado": "Sentencia definitiva del 12 sep 2026", "numero": "Toca 512/2026 · 9/2026"}

    expediente = forms.ModelChoiceField(label="Expediente", queryset=Expediente.objects.none(), empty_label=None)
    tipo = forms.ChoiceField(label="Tipo de recurso", choices=_opciones(RECURSOS), initial="Apelación")
    promovente = forms.ChoiceField(label="Quién lo promueve", choices=_opciones(PROMOVENTES), initial="Nosotros")
    acto_impugnado = forms.CharField(label="Acto o resolución impugnada", required=False, max_length=300)
    numero = forms.CharField(label="Toca o número de expediente", required=False, max_length=60)
    organo = forms.CharField(label="Órgano que lo resuelve", required=False, max_length=200)
    fecha_interposicion = forms.DateField(label="Fecha de interposición", required=False, widget=FechaInput())
    etapa = forms.ChoiceField(label="Etapa actual", choices=[])
    suspension = forms.ChoiceField(
        label="Suspensión (amparo indirecto)", choices=_opciones(SUSPENSION), initial="No aplica"
    )
    notas = forms.CharField(label="Notas", required=False, widget=forms.Textarea)

    def __init__(self, *a, con_expediente=False, **kw):
        super().__init__(*a, **kw)
        if con_expediente:
            self.fields["expediente"].queryset = Expediente.objects.select_related("cliente")
            self.fields["expediente"].label_from_instance = lambda e: f"{e.numero} · {e.cliente.razon}"
        else:
            del self.fields["expediente"]
        tipo = self.data.get("tipo") or self.initial.get("tipo") or "Apelación"
        cfg = RECURSOS.get(tipo, RECURSOS["Apelación"])
        self.fields["etapa"].choices = _opciones(cfg["etapas"])
        if not self.initial.get("organo"):
            self.fields["organo"].initial = cfg["organo"]
        self.fields["tipo"].widget.attrs["data-recurso-tipo"] = "1"


class ResolverForm(FormDespacho):
    resultado = forms.ChoiceField(
        label="Resultado para nuestro cliente", choices=_opciones(RESULTADOS), initial="Favorable"
    )
    fecha = forms.DateField(label="Fecha de la resolución", widget=FechaInput())
    sintesis = forms.CharField(
        label="Síntesis de la resolución",
        required=False,
        widget=forms.Textarea(attrs={"placeholder": "Se confirma la sentencia de primera instancia…"}),
    )
    etapa_exp = forms.ChoiceField(label="Etapa del expediente principal después de esto", choices=_opciones(ETAPAS))
