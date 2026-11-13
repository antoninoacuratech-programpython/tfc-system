"""Cópias de segurança do SGTF.

Gera um ZIP com:
  - dados.json   todos os dados (formato do `dumpdata` do Django)
  - media/...    opcional: os ficheiros carregados (PDFs, fotografias)
  - LEIAME.txt   como repor a cópia

Usado pela página de administração (/backups/) e pelo comando `manage.py backup_sgtf`.
"""

import io
import json
import os
import zipfile
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.utils import timezone

# Tabelas que o Django recria sozinho ou que não interessam numa cópia.
EXCLUIR = ["contenttypes", "auth.permission", "sessions", "admin.logentry"]

LEIAME = """SGTF — Cópia de segurança
Instituição: {instituicao}
Criada em:   {data}
Registos:    {registos}
Ficheiros:   {ficheiros}

COMO REPOR (num servidor com o SGTF instalado e a base de dados vazia)
  1. Extrair este ZIP.
  2. python manage.py migrate
  3. python manage.py loaddata dados.json
  4. Se a cópia incluir a pasta media/, copiá-la para a pasta media do projecto.

ATENÇÃO: este ficheiro contém dados pessoais e as senhas cifradas de todos
os utilizadores. Guarde-o em local seguro e não o partilhe.
"""


def nome_ficheiro(agora=None):
    agora = timezone.localtime(agora or timezone.now())
    return f"sgtf-backup-{agora:%Y%m%d-%H%M}.zip"


def exportar_dados():
    """Devolve (json_texto, numero_de_registos)."""
    saida = io.StringIO()
    call_command(
        "dumpdata",
        "--natural-foreign",
        "--indent", "1",
        *[f"--exclude={e}" for e in EXCLUIR],
        stdout=saida,
    )
    texto = saida.getvalue()
    return texto, len(json.loads(texto))


def ficheiros_media():
    raiz = Path(settings.MEDIA_ROOT)
    if not raiz.is_dir():
        return []
    return [p for p in raiz.rglob("*") if p.is_file()]


def gerar_zip(incluir_media=False):
    """Cria o ZIP em memória. Devolve (bytes, info)."""
    texto, n_registos = exportar_dados()
    media = ficheiros_media() if incluir_media else []
    raiz_media = Path(settings.MEDIA_ROOT)
    agora = timezone.now()

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("dados.json", texto)
        for caminho in media:
            zf.write(caminho, arcname=(Path("media") / caminho.relative_to(raiz_media)).as_posix())
        zf.writestr("LEIAME.txt", LEIAME.format(
            instituicao=settings.INSTITUICAO_NOME,
            data=f"{timezone.localtime(agora):%d/%m/%Y %H:%M}",
            registos=n_registos,
            ficheiros=f"{len(media)} incluídos" if incluir_media else "não incluídos",
        ))
    conteudo = buffer.getvalue()
    info = {
        "nome": nome_ficheiro(agora),
        "registos": n_registos,
        "ficheiros": len(media),
        "tamanho": len(conteudo),
        "incluiu_media": incluir_media,
    }
    return conteudo, info


def tamanho_legivel(n):
    for unidade in ("B", "KB", "MB", "GB"):
        if n < 1024 or unidade == "GB":
            return f"{n:.0f} {unidade}" if unidade == "B" else f"{n:.1f} {unidade}"
        n /= 1024


def resumo_sistema():
    """Números mostrados na página antes de criar a cópia."""
    from .models import InscricaoTFC, Predefesa, Tema, Usuario

    media = ficheiros_media()
    return {
        "utilizadores": Usuario.objects.count(),
        "temas": Tema.objects.count(),
        "inscricoes": InscricaoTFC.objects.count(),
        "predefesas": Predefesa.objects.count(),
        "ficheiros": len(media),
        "tamanho_media": tamanho_legivel(sum(os.path.getsize(p) for p in media)),
    }
