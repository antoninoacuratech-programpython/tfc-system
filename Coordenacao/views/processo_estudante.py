"""Página «Processo do estudante» e ZIP com toda a documentação."""

from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from .. import processo_estudante as proc
from ..models import Usuario
from ..permissions import PERFIL_COORDENACAO, PERFIS_GESTAO, perfil_requerido


def _estudante_acessivel(request, estudante_id):
    estudante = get_object_or_404(Usuario.objects.select_related("curso"), pk=estudante_id, perfil="estudante")
    user = request.user
    # a coordenação só vê os estudantes do seu curso
    if not user.is_superuser and user.perfil == PERFIL_COORDENACAO and user.curso_id and estudante.curso_id != user.curso_id:
        raise PermissionDenied("Este estudante não pertence ao seu curso.")
    return estudante


@perfil_requerido(*PERFIS_GESTAO)
def processo_estudante(request, estudante_id):
    dados = proc.recolher(_estudante_acessivel(request, estudante_id))
    pastas = {}
    for d in dados["documentos"]:
        pastas.setdefault(d["pasta"], []).append(d)
    dados["pastas"] = sorted(pastas.items())
    return render(request, "admin/processo_estudante.html", dados)


@perfil_requerido(*PERFIS_GESTAO)
def processo_estudante_zip(request, estudante_id):
    estudante = _estudante_acessivel(request, estudante_id)
    conteudo, _ = proc.gerar_zip(request, proc.recolher(estudante))
    resposta = HttpResponse(conteudo, content_type="application/zip")
    resposta["Content-Disposition"] = f'attachment; filename="{proc.nome_zip(estudante)}"'
    return resposta


@perfil_requerido(*PERFIS_GESTAO)
def perfil_documental(request, estudante_id):
    # o antigo «dossiê» passou a ser a página do processo
    return redirect("processo_estudante", estudante_id)
