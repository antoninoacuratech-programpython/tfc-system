"""Entrega dos ficheiros guardados na base de dados."""

import io
import posixpath

from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from ..models import Ficheiro

# só estes abrem no navegador; o resto (html, svg, ...) é sempre descarregado
TIPOS_EM_LINHA = {"application/pdf", "image/png", "image/jpeg", "image/gif", "image/webp"}


@login_required
@require_GET
def servir_ficheiro(request, nome):
    registo = Ficheiro.objects.filter(nome=posixpath.normpath(nome).lstrip("/")).first()
    if registo is None:
        raise Http404("Ficheiro não encontrado.")
    tipo = registo.tipo or "application/octet-stream"
    resposta = FileResponse(
        io.BytesIO(bytes(registo.conteudo)),
        content_type=tipo,
        as_attachment=tipo not in TIPOS_EM_LINHA,
        filename=posixpath.basename(registo.nome),
    )
    resposta["Cache-Control"] = "private, max-age=3600"
    return resposta
