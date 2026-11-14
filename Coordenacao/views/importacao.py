"""Importação de estudantes do sistema de gestão escolar."""

from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import redirect, render

from .. import importacao as imp
from ..models import Curso
from ..permissions import PERFIL_COORDENACAO, perfil_requerido

SESSAO = "importacao_estudantes"


def _cursos(user):
    if user.is_superuser or not user.curso_id:
        return Curso.objects.select_related("departamento").order_by("nome")
    return Curso.objects.filter(pk=user.curso_id)


@perfil_requerido(PERFIL_COORDENACAO)
def importar_estudantes(request):
    cursos = _cursos(request.user)
    contexto = {"cursos": cursos, "max_linhas": imp.MAX_LINHAS}

    if request.method == "POST" and request.POST.get("acao") == "analisar":
        curso = cursos.filter(pk=request.POST.get("curso")).first() or (cursos.first() if cursos.count() == 1 else None)
        usar_coluna = bool(request.POST.get("usar_coluna_curso")) and request.user.is_superuser
        if not curso and not usar_coluna:
            messages.error(request, "Escolha o curso dos estudantes.")
            return render(request, "importacao/importar.html", contexto)
        try:
            registos = imp.analisar(imp.ler_ficheiro(request.FILES.get("ficheiro")), curso, cursos, usar_coluna)
        except imp.ErroImportacao as erro:
            messages.error(request, str(erro))
            return render(request, "importacao/importar.html", contexto)

        request.session[SESSAO] = {"registos": registos, "curso": curso.pk if curso else None, "coluna": usar_coluna}
        contexto.update({
            "registos": registos,
            "curso": curso,
            "novos": sum(1 for r in registos if r["estado"] == "novo"),
            "existentes": sum(1 for r in registos if r["estado"] == "existe"),
            "erros": sum(1 for r in registos if r["estado"] == "erro"),
        })
        return render(request, "importacao/previsualizar.html", contexto)

    if request.method == "POST" and request.POST.get("acao") == "confirmar":
        guardado = request.session.pop(SESSAO, None)
        if not guardado:
            messages.error(request, "A pré-visualização expirou. Carregue o ficheiro outra vez.")
            return redirect("importar_estudantes")
        curso = cursos.filter(pk=guardado["curso"]).first() if guardado["curso"] else None
        # volta a verificar: alguém pode ter criado contas entretanto
        registos = imp.analisar(guardado["registos"], curso, cursos, guardado["coluna"])
        criados = imp.criar_contas(registos)
        ignorados = len(registos) - len(criados)
        if criados:
            messages.success(request, f"{len(criados)} estudante(s) importado(s) com conta activa.")
        if ignorados:
            messages.info(request, f"{ignorados} linha(s) ignorada(s): já tinham conta ou tinham erros.")
        # as senhas temporárias só existem nesta resposta; não ficam guardadas em lado nenhum
        resposta = render(request, "importacao/resultado.html", {"criados": criados})
        resposta["Cache-Control"] = "no-store"
        return resposta

    return render(request, "importacao/importar.html", contexto)


@perfil_requerido(PERFIL_COORDENACAO)
def modelo_importacao(request):
    resposta = HttpResponse("﻿" + imp.MODELO_CSV, content_type="text/csv; charset=utf-8")
    resposta["Content-Disposition"] = 'attachment; filename="modelo_importacao_estudantes.csv"'
    return resposta
