from django.core.management.base import BaseCommand

from nucleo import respaldos


class Command(BaseCommand):
    help = "Respaldo externo: volcado de la base, ancla de auditoría, réplica de PDF y depuración de respaldos viejos."

    def add_arguments(self, parser):
        parser.add_argument("--sin-pdf", action="store_true", help="No replicar los PDF")

    def handle(self, *args, sin_pdf=False, **opts):
        malo = respaldos.verificar_y_avisar()
        self.stdout.write("Cadena de auditoría: " + ("íntegra" if malo is None else f"ROTA en el evento {malo}"))
        clave, tamano = respaldos.respaldar_bd()
        self.stdout.write(f"Base respaldada en {clave} ({tamano:,} bytes)")
        if not sin_pdf:
            self.stdout.write(f"PDF replicados: {respaldos.replicar_pdf()}")
        self.stdout.write(f"Respaldos depurados: {len(respaldos.depurar_respaldos())}")
