from django.core.management.base import BaseCommand, CommandError

from nucleo.respaldos import verificar_y_avisar


class Command(BaseCommand):
    help = "Verifica la cadena de hashes de la bitácora de auditoría y avisa a los administradores si está rota."

    def handle(self, *args, **opts):
        malo = verificar_y_avisar()
        if malo is not None:
            raise CommandError(f"Cadena rota a partir del evento {malo}")
        self.stdout.write(self.style.SUCCESS("Cadena de auditoría íntegra"))
