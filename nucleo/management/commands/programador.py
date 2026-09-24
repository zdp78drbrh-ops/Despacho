"""Proceso 'worker' del hosting: ejecuta las tareas diarias a su hora (Ciudad de México).
Fase 1: respaldo a las 02:00. Fase 2 añadirá los avisos de plazos a las 07:00."""

import logging
import time

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import close_old_connections
from django.utils import timezone

log = logging.getLogger(__name__)

TAREAS = [("02:00", "respaldar", []), ("03:00", "clearsessions", [])]


class Command(BaseCommand):
    help = "Ejecuta las tareas programadas (dejar corriendo como proceso aparte)."

    def handle(self, *args, **opts):
        hechas = set()
        self.stdout.write("Programador iniciado: " + ", ".join(f"{h} {c}" for h, c, _ in TAREAS))
        while True:
            ahora = timezone.localtime()
            for hora, comando, argumentos in TAREAS:
                marca = (ahora.date(), comando)
                if ahora.strftime("%H:%M") >= hora and marca not in hechas:
                    hechas.add(marca)
                    if ahora.strftime("%H:%M") > _mas_una_hora(hora):
                        continue  # arrancó tarde: no correr en horario laboral; toca mañana
                    close_old_connections()
                    try:
                        call_command(comando, *argumentos)
                    except Exception:
                        log.exception("Falló la tarea %s", comando)
            hechas = {m for m in hechas if m[0] == ahora.date()}
            time.sleep(30)


def _mas_una_hora(hora):
    h, m = map(int, hora.split(":"))
    return f"{min(h + 1, 23):02d}:{m:02d}"
