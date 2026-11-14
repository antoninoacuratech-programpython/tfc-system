"""Sessão de pré-defesa: abertura pelo secretário, recomendações da banca e encerramento."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import NotificacaoFinal, Predefesa, Recomendacao, Usuario
from ..permissions import PERFIS_GESTAO, tem_perfil


def _predefesa(pk):
    return get_object_or_404(
        Predefesa.objects.select_related("estudante__curso", "tema__tutor_indicado", "tema__processo",
                                         "presidente", "secretario", "primeiro_vogal", "segundo_vogal"),
        pk=pk,
    )


def _na_mesa(user, p):
    return bool(p.funcao_de(user))


def _conduz(user, p):
    """Quem abre e encerra: o secretário (ou o presidente, se não houver secretário)."""
    if user.is_superuser:
        return True
    if p.secretario_id:
        return user.pk in (p.secretario_id, p.presidente_id)
    return user.pk == p.presidente_id


def _pode_ver(user, p):
    if user.is_superuser or _na_mesa(user, p) or tem_perfil(user, *PERFIS_GESTAO):
        return True
    return bool(p.tema and p.tema.tutor_indicado_id == user.pk)


def _nome(u):
    return f"{u.nome} {u.sobrenome}" if u else ""


@login_required
def sessao_predefesa(request, pk):
    p = _predefesa(pk)
    if not _pode_ver(request.user, p):
        raise PermissionDenied("Não faz parte desta banca.")

    recs = list(p.recomendacoes.select_related("autor").order_by("data_criacao"))
    mesa = []
    for funcao, chave, docente in p.mesa():
        if not docente:
            continue
        mesa.append({
            "funcao": funcao, "chave": chave, "docente": docente,
            "presente": chave in (p.presentes or []),
            "fortes": [r for r in recs if r.autor_id == docente.pk and r.tipo == "forte"],
            "melhorias": [r for r in recs if r.autor_id == docente.pk and r.tipo == "melhoria"],
        })

    na_mesa = _na_mesa(request.user, p)
    em_curso = bool(p.aberta_em and not p.encerrada_em)
    if request.user.is_superuser:
        base = "admin/base.html"
    elif request.user.perfil == "tutor":
        base = "tutor/base.html"
    else:
        base = "admin/base.html"
    return render(request, "predefesa/sessao.html", {
        "p": p,
        "base": base,
        "mesa": mesa,
        "conduz": _conduz(request.user, p),
        "pode_registar": em_curso and (na_mesa or request.user.is_superuser),
        "em_curso": em_curso,
        "minha_funcao": p.funcao_de(request.user),
        "total_melhorias": sum(1 for r in recs if r.tipo == "melhoria"),
        "total_fortes": sum(1 for r in recs if r.tipo == "forte"),
        "resultados": Predefesa.RESULTADOS,
    })


@login_required
@require_POST
def abrir_sessao_predefesa(request, pk):
    p = _predefesa(pk)
    if not _conduz(request.user, p):
        raise PermissionDenied("Só o secretário da banca abre a sessão.")
    if p.aberta_em:
        messages.info(request, "A sessão já foi aberta.")
        return redirect("sessao_predefesa", pk)

    chaves_validas = {chave for _, chave, docente in p.mesa() if docente}
    presentes = [c for c in request.POST.getlist("presentes") if c in chaves_validas]
    if not presentes:
        messages.error(request, "Marque os membros da banca que estão presentes.")
        return redirect("sessao_predefesa", pk)

    Predefesa.objects.filter(pk=p.pk).update(aberta_em=timezone.now(), presentes=presentes)
    messages.success(request, "Sessão aberta. A banca já pode registar as recomendações.")
    return redirect("sessao_predefesa", pk)


@login_required
@require_POST
def registar_recomendacao_banca(request, pk):
    p = _predefesa(pk)
    if not p.aberta_em or p.encerrada_em:
        messages.error(request, "Só se registam recomendações com a sessão aberta.")
        return redirect("sessao_predefesa", pk)
    if not p.tema_id:
        messages.error(request, "Esta pré-defesa não tem tema associado.")
        return redirect("sessao_predefesa", pk)

    autor, funcao = request.user, p.funcao_de(request.user)
    # o secretário pode registar em nome de qualquer membro presente
    chave = request.POST.get("membro", "")
    if chave and _conduz(request.user, p):
        escolhido = next(((f, d) for f, c, d in p.mesa() if c == chave and d), None)
        if escolhido:
            funcao, autor = escolhido
    if not funcao:
        raise PermissionDenied("Não faz parte desta banca.")

    tipo = request.POST.get("tipo")
    texto = request.POST.get("texto", "").strip()
    if tipo not in ("forte", "melhoria") or not texto:
        messages.error(request, "Escolha o tipo e escreva a recomendação.")
        return redirect("sessao_predefesa", pk)

    Recomendacao.objects.create(
        tema=p.tema, predefesa=p, autor=autor, funcao_autor=funcao,
        tipo=tipo, texto=texto[:3000], lida=False,
    )
    messages.success(request, f"Registado em nome de {_nome(autor)} ({funcao}).")
    return redirect(f"{reverse('sessao_predefesa', args=[pk])}#membro-{autor.pk}")


@login_required
@require_POST
def eliminar_recomendacao_banca(request, pk, rec_id):
    p = _predefesa(pk)
    rec = get_object_or_404(Recomendacao, pk=rec_id, predefesa=p)
    if p.encerrada_em:
        messages.error(request, "A sessão já foi encerrada; as recomendações não podem ser alteradas.")
    elif rec.autor_id == request.user.pk or _conduz(request.user, p):
        rec.delete()
        messages.success(request, "Recomendação retirada.")
    else:
        raise PermissionDenied
    return redirect("sessao_predefesa", pk)


@login_required
@require_POST
def encerrar_sessao_predefesa(request, pk):
    p = _predefesa(pk)
    if not _conduz(request.user, p):
        raise PermissionDenied("Só o secretário da banca encerra a sessão.")
    if not p.aberta_em or p.encerrada_em:
        messages.error(request, "A sessão não está em curso.")
        return redirect("sessao_predefesa", pk)

    resultado = request.POST.get("resultado")
    if resultado not in dict(Predefesa.RESULTADOS):
        messages.error(request, "Indique o resultado da pré-defesa.")
        return redirect("sessao_predefesa", pk)

    Predefesa.objects.filter(pk=p.pk).update(
        encerrada_em=timezone.now(), resultado=resultado,
        observacoes_sessao=request.POST.get("observacoes", "").strip()[:3000],
    )
    rotulo = dict(Predefesa.RESULTADOS)[resultado]
    n = p.recomendacoes.filter(tipo="melhoria").count()
    estudante = p.estudante
    NotificacaoFinal.objects.create(
        usuario=estudante, titulo="Resultado da pré-defesa",
        mensagem=f"Resultado: {rotulo}. A banca deixou {n} recomendaç{'ão' if n == 1 else 'ões'} a cumprir.",
        link=reverse("todas_recomendacoes"),
    )
    if p.tema and p.tema.tutor_indicado:
        NotificacaoFinal.objects.create(
            usuario=p.tema.tutor_indicado, titulo="Recomendações da pré-defesa",
            mensagem=f"{_nome(estudante)}: {rotulo}. Acompanhe o cumprimento de {n} recomendaç{'ão' if n == 1 else 'ões'}.",
            link=reverse("tutor_recomendacao", args=[p.tema_id]),
        )
    if estudante.curso_id:
        for coord in Usuario.objects.filter(perfil="cordenacao", curso_id=estudante.curso_id, estado_user="activo"):
            NotificacaoFinal.objects.create(
                usuario=coord, titulo="Pré-defesa encerrada",
                mensagem=f"{_nome(estudante)}: {rotulo}.", link=reverse("sessao_predefesa", args=[p.pk]),
            )
    messages.success(request, f"Sessão encerrada ({rotulo}). O estudante e o orientador foram notificados.")
    return redirect("sessao_predefesa", pk)
