"""Texto del botón "Informe al cliente" (informeExpediente del prototipo), palabra por palabra."""

from nucleo.fechas import fmt


def informe_expediente(e, firmante):
    u = e.ultima()
    pend = e.pendientes()
    rec = e.recursos_activos()
    partes = [
        "Estimado cliente:\n\n",
        f"Le comparto el estado del asunto {e.numero}, {e.tipo or e.materia}, que se tramita ante el {e.juzgado}, "
        f"en el que usted comparece como {(e.caracter or 'parte').lower()} frente a {e.contraparte or 'la contraparte'}.\n\n",
        f"El expediente se encuentra en la etapa de {e.etapa.lower()}.",
    ]
    if e.audiencia:
        partes.append(f" La próxima audiencia está señalada para el {fmt(e.audiencia, True)}.")
    if rec:
        lineas = []
        for x in rec:
            s = f"- {x.titulo}, {x.organo or ''}: {x.etapa.lower()}"
            if x.tipo == "Amparo indirecto" and x.suspension and x.suspension != "No aplica":
                s += f" (suspensión {x.suspension.lower()})"
            lineas.append(s)
        partes.append("\n\nRecursos en trámite:\n" + "\n".join(lineas))
    ult = f"{fmt(u.fecha, True)}, {u.texto.lower()}." if u else "sin actuaciones recientes."
    partes.append(f"\n\nÚltima actuación: {ult}\n\n")
    if pend:
        partes.append(
            "Lo que sigue:\n" + "\n".join(f"- {a.titulo}{f' ({fmt(a.plazo, True)})' if a.plazo else ''}" for a in pend)
        )
    else:
        partes.append("Por el momento estamos en espera de que el juzgado acuerde lo conducente.")
    partes.append(f"\n\nQuedo atento a cualquier duda.\n\n{firmante}")
    return "".join(partes)
