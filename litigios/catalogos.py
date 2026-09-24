"""Catálogos copiados literalmente del prototipo (docs/referencia/prototipo.html)."""

MATERIAS = ["Civil", "Mercantil", "Familiar", "Penal", "Amparo", "Laboral", "Administrativo"]
ETAPAS = [
    "Presentación de demanda",
    "Emplazamiento",
    "Contestación",
    "Audiencia preliminar",
    "Desahogo de pruebas",
    "Alegatos",
    "Citado a sentencia",
    "Sentencia",
    "Apelación",
    "Amparo",
    "Ejecución",
    "Convenio",
]
TIPOS_ACCION = ["Promoción", "Escrito", "Acto procesal", "Diligencia", "Gestión", "Audiencia"]
CARACTERES = ["Actor", "Demandado", "Quejoso", "Tercero interesado", "Imputado", "Víctima", "Promovente"]

# estado: (etiqueta, clase del chip)
EST_ACC = {
    "pendiente": ("Pendiente", "gry"),
    "elaboracion": ("En elaboración", "blu"),
    "revision": ("En revisión", "amb"),
    "aprobada": ("Aprobada", "grn"),
    "terminada": ("Terminada", "grn"),
}
FLUJO_ACC = ["pendiente", "elaboracion", "revision", "aprobada", "terminada"]

RECURSOS = {
    "Apelación": {
        "organo": "Sala Civil del Tribunal Superior de Justicia",
        "etapas": [
            "Interposición del recurso",
            "Admisión y efectos",
            "Expresión de agravios",
            "Contestación de agravios",
            "Remisión a la Sala",
            "Radicación del toca",
            "Citación para sentencia",
            "Sentencia de segunda instancia",
            "Devolución al juzgado de origen",
        ],
    },
    "Amparo directo": {
        "organo": "Tribunal Colegiado de Circuito",
        "etapas": [
            "Presentación ante la autoridad responsable",
            "Remisión al Tribunal Colegiado",
            "Admisión o prevención",
            "Amparo adhesivo (15 días)",
            "Pedimento del Ministerio Público",
            "Turno a ponencia",
            "Sentencia de amparo",
            "Cumplimiento de la ejecutoria",
        ],
    },
    "Amparo indirecto": {
        "organo": "Juzgado de Distrito",
        "etapas": [
            "Presentación de la demanda",
            "Admisión y suspensión provisional",
            "Audiencia incidental y suspensión definitiva",
            "Informes justificados",
            "Audiencia constitucional",
            "Sentencia",
            "Recurso de revisión",
            "Cumplimiento de la ejecutoria",
        ],
    },
    "Recurso de revisión (amparo)": {
        "organo": "Tribunal Colegiado de Circuito",
        "etapas": ["Interposición del recurso", "Admisión", "Turno a ponencia", "Sentencia"],
    },
    "Queja": {
        "organo": "Tribunal Colegiado de Circuito",
        "etapas": ["Interposición del recurso", "Admisión", "Resolución"],
    },
    "Revocación o reposición": {
        "organo": "Mismo juzgado",
        "etapas": ["Interposición del recurso", "Vista a la contraparte", "Resolución"],
    },
}
SUSPENSION = ["No aplica", "Solicitada", "Provisional concedida", "Definitiva concedida", "Negada"]
RESULTADOS = ["Favorable", "Parcialmente favorable", "Desfavorable", "Desechado", "Sobreseído", "Desistido"]
PROMOVENTES = ["Nosotros", "Contraparte"]

ESTADOS_EXP = {"activo": "Activo", "sentencia": "En espera de sentencia", "terminado": "Terminado"}
