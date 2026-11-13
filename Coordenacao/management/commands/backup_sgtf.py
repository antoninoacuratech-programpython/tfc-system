"""python manage.py backup_sgtf [--media] [--pasta CAMINHO]

Cria uma cópia de segurança (ZIP) igual à da página de administração.
"""

from pathlib import Path

from django.core.management.base import BaseCommand

from Coordenacao.backup import gerar_zip, tamanho_legivel
from Coordenacao.models import RegistoBackup


class Command(BaseCommand):
    help = "Cria uma cópia de segurança completa do SGTF (ZIP com dados.json e, opcionalmente, os ficheiros)."

    def add_arguments(self, parser):
        parser.add_argument("--media", action="store_true", help="Incluir os ficheiros carregados (pasta media).")
        parser.add_argument("--pasta", default="backups", help="Pasta onde guardar o ZIP (por omissão: ./backups).")

    def handle(self, *args, **opts):
        conteudo, info = gerar_zip(incluir_media=opts["media"])
        pasta = Path(opts["pasta"])
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / info["nome"]
        destino.write_bytes(conteudo)
        RegistoBackup.objects.create(
            utilizador=None, nome_ficheiro=info["nome"], registos=info["registos"],
            ficheiros=info["ficheiros"], tamanho=info["tamanho"], incluiu_media=opts["media"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Cópia criada: {destino} ({info['registos']} registos, {info['ficheiros']} ficheiros, {tamanho_legivel(info['tamanho'])})"
        ))
