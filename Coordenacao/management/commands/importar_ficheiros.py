"""python manage.py importar_ficheiros [--pasta media] [--todos]

Copia ficheiros de uma pasta (a media/ antiga ou a de uma cópia de segurança)
para o armazenamento actual. Por omissão só importa os que algum registo usa.
"""

from pathlib import Path

from django.apps import apps
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand, CommandError
from django.db import models


def nomes_em_uso():
    nomes = set()
    for modelo in apps.get_models():
        campos = [c.name for c in modelo._meta.get_fields() if isinstance(c, models.FileField)]
        for campo in campos:
            nomes.update(n for n in modelo.objects.exclude(**{campo: ""}).exclude(**{f"{campo}__isnull": True})
                         .values_list(campo, flat=True) if n)
    return nomes


class Command(BaseCommand):
    help = "Importa ficheiros de uma pasta para o armazenamento do SGTF (base de dados na Render)."

    def add_arguments(self, parser):
        parser.add_argument("--pasta", default="media")
        parser.add_argument("--todos", action="store_true", help="Importar também ficheiros sem registo associado.")

    def handle(self, *args, **opts):
        raiz = Path(opts["pasta"])
        if not raiz.is_dir():
            raise CommandError(f"A pasta {raiz} não existe.")
        em_uso = None if opts["todos"] else nomes_em_uso()
        importados = ignorados = existentes = 0
        for caminho in sorted(p for p in raiz.rglob("*") if p.is_file()):
            nome = caminho.relative_to(raiz).as_posix()
            if em_uso is not None and nome not in em_uso:
                ignorados += 1
                continue
            if default_storage.exists(nome):
                existentes += 1
                continue
            default_storage._save(nome, ContentFile(caminho.read_bytes(), name=nome))
            importados += 1
        self.stdout.write(self.style.SUCCESS(
            f"Importados: {importados} · já existiam: {existentes} · sem registo (ignorados): {ignorados}"
        ))
