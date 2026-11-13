"""Cópias de segurança (apenas para o superadministrador)."""

import logging

from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_POST

from ..backup import gerar_zip, resumo_sistema, tamanho_legivel
from ..models import RegistoBackup
from ..permissions import superuser_requerido

logger = logging.getLogger(__name__)


@superuser_requerido
def backups(request):
    historico = list(RegistoBackup.objects.select_related("utilizador")[:20])
    for r in historico:
        r.tamanho_legivel = tamanho_legivel(r.tamanho)
    return render(request, "admin/backups.html", {
        "resumo": resumo_sistema(),
        "historico": historico,
    })


@superuser_requerido
@require_POST
def criar_backup(request):
    incluir_media = request.POST.get("incluir_media") == "1"
    conteudo, info = gerar_zip(incluir_media=incluir_media)
    RegistoBackup.objects.create(
        utilizador=request.user,
        nome_ficheiro=info["nome"],
        registos=info["registos"],
        ficheiros=info["ficheiros"],
        tamanho=info["tamanho"],
        incluiu_media=incluir_media,
    )
    logger.info("Cópia de segurança %s criada por %s", info["nome"], request.user.email)
    resposta = HttpResponse(conteudo, content_type="application/zip")
    resposta["Content-Disposition"] = f'attachment; filename="{info["nome"]}"'
    resposta["Content-Length"] = str(info["tamanho"])
    return resposta
