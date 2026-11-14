"""Assistente de IA: proposta de tema, temas parecidos, tutores sugeridos e resumo para o júri."""

import json

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..ia import ErroIA, assistente_proposta, ia_disponivel, resumo_para_juri
from ..models import Predefesa, ResumoIA, Tema
from ..permissions import PERFIL_ESTUDANTE, PERFIS_GESTAO, perfil_requerido, tem_perfil
from ..similaridade import sugerir_tutores, temas_semelhantes


def _dados_json(request):
    try:
        return json.loads(request.body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return {}


def _consumir_quota(user):
    # limite simples por utilizador e por hora, para controlar o custo da API
    chave = f"ia:{user.pk}:{timezone.now():%Y%m%d%H}"
    usados = cache.get(chave, 0)
    if usados >= settings.IA_LIMITE_POR_HORA:
        return False
    cache.set(chave, usados + 1, 3600)
    return True


@perfil_requerido(PERFIL_ESTUDANTE)
@require_POST
def ia_proposta(request):
    if not ia_disponivel():
        return JsonResponse({"ok": False, "erro": "O assistente de IA ainda não está configurado neste servidor."}, status=503)
    if not _consumir_quota(request.user):
        return JsonResponse({"ok": False, "erro": "Atingiu o limite de pedidos ao assistente nesta hora. Tente mais tarde."}, status=429)
    ideia = _dados_json(request).get("ideia", "")
    curso = request.user.curso.nome.strip() if request.user.curso else ""
    try:
        return JsonResponse({"ok": True, **assistente_proposta(ideia, curso)})
    except ErroIA as e:
        return JsonResponse({"ok": False, "erro": str(e)}, status=400)


@perfil_requerido(PERFIL_ESTUDANTE, *PERFIS_GESTAO)
@require_POST
def ia_analise(request):
    dados = _dados_json(request)
    titulo = str(dados.get("titulo", ""))[:300]
    descricao = str(dados.get("descricao", ""))[:5000]
    excluir = request.user.pk if request.user.perfil == PERFIL_ESTUDANTE else None
    return JsonResponse({
        "ok": True,
        "semelhantes": temas_semelhantes(titulo, descricao, excluir_estudante_id=excluir),
        "tutores": sugerir_tutores(titulo, descricao),
    })


def _pode_ver_resumo(user, tema):
    if tem_perfil(user, *PERFIS_GESTAO):
        return True
    if user.perfil != "tutor":
        return False
    if tema.tutor_indicado_id == user.pk:
        return True
    return Predefesa.objects.filter(tema=tema).filter(
        Q(presidente=user) | Q(secretario=user) | Q(primeiro_vogal=user) | Q(segundo_vogal=user)
    ).exists()


@perfil_requerido("tutor", *PERFIS_GESTAO)
def resumo_juri(request, tema_id):
    tema = get_object_or_404(Tema.objects.select_related("estudante__curso", "tutor_indicado"), pk=tema_id)
    if not _pode_ver_resumo(request.user, tema):
        raise PermissionDenied("Só a gestão e os membros do júri podem ver este resumo.")

    if request.method == "POST":
        if not ia_disponivel():
            messages.error(request, "O assistente de IA ainda não está configurado neste servidor.")
        elif not _consumir_quota(request.user):
            messages.error(request, "Atingiu o limite de pedidos ao assistente nesta hora. Tente mais tarde.")
        else:
            try:
                conteudo = resumo_para_juri(tema)
                ResumoIA.objects.update_or_create(tema=tema, defaults={"conteudo": conteudo, "gerado_por": request.user})
                messages.success(request, "Resumo gerado. Reveja-o antes de o usar: foi feito por IA.")
            except ErroIA as e:
                messages.error(request, str(e))
        return redirect("resumo_juri", tema_id=tema.pk)

    predefesa = Predefesa.objects.filter(tema=tema).select_related(
        "presidente", "secretario", "primeiro_vogal", "segundo_vogal"
    ).order_by("-data").first()
    return render(request, "ia/resumo_juri.html", {
        "tema": tema,
        "predefesa": predefesa,
        "resumo": ResumoIA.objects.filter(tema=tema).select_related("gerado_por").first(),
        "base_template": "tutor/base.html" if request.user.perfil == "tutor" else "admin/base.html",
    })


@perfil_requerido("tutor")
def minhas_bancas(request):
    u = request.user
    bancas = list(
        Predefesa.objects.filter(Q(presidente=u) | Q(secretario=u) | Q(primeiro_vogal=u) | Q(segundo_vogal=u))
        .select_related("estudante__curso", "tema").order_by("-data", "-hora")
    )
    for b in bancas:
        b.funcao = ("Presidente" if b.presidente_id == u.pk else "Secretário" if b.secretario_id == u.pk
                    else "1.º vogal" if b.primeiro_vogal_id == u.pk else "2.º vogal")
    return render(request, "ia/minhas_bancas.html", {"bancas": bancas, "hoje": timezone.localdate()})
