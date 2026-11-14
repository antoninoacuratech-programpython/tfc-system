"""python manage.py alertas_progresso — pode ser agendado (cron) uma vez por dia."""

from django.core.management.base import BaseCommand

from Coordenacao.progresso import gerar_alertas


class Command(BaseCommand):
    help = "Envia as notificações de prazos a terminar, etapas em atraso e estudantes parados."

    def handle(self, *args, **opts):
        c = gerar_alertas()
        self.stdout.write(self.style.SUCCESS(
            f"Prazos a terminar: {c['prazo']} · em atraso: {c['atraso']} · parados: {c['parado']}"
        ))
