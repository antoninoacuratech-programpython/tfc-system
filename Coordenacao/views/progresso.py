"""Acompanhamento do progresso do TFC: etapas, entregas e avaliação pelo tutor."""

from datetime import date, timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import EtapaTrabalho, NotificacaoFinal, PlanoTrabalho, Tema
from ..permissions import PERFIL_ESTUDANTE, PERFIL_TUTOR, PERFIS_GESTAO, perfil_requerido, tem_perfil
from ..progresso import PLANO_PADRAO, resumo

EXTENSOES_ENTREGA = (".pdf", ".doc", ".docx", ".odt", ".zip", ".rar", ".pptx")
TAMANHO_MAX_ENTREGA = 20 * 1024 * 1024


def _temas_aprovados():
    return Tema.objects.filter(status_final="aprovado").select_related(
        "estudante__curso", "tutor_indicado", "plano"
    ).prefetch_related("plano__etapas")


def _plano_de(tema):
    try:
        return tema.plano
    except PlanoTrabalho.DoesNotExist:
        return None


def _linhas(temas):
    linhas = [{"tema": t, "info": resumo(_plano_de(t))} for t in temas]
    ordem = {"parado": 0, "atrasado": 1, "sem_plano": 2, "em_dia": 3, "concluido": 4}
    linhas.sort(key=lambda l: (ordem[l["info"]["estado"]], l["tema"].estudante.nome))
    return linhas


def _contagem(linhas):
    c = {"total": len(linhas), "em_dia": 0, "atrasado": 0, "parado": 0, "sem_plano": 0, "concluido": 0}
    for l in linhas:
        c[l["info"]["estado"]] += 1
    return c


def _data(valor):
    try:
        return date.fromisoformat(valor or "")
    except ValueError:
        return None


def _avisar(usuario, titulo, mensagem, link):
    if usuario:
        NotificacaoFinal.objects.create(usuario=usuario, titulo=titulo, mensagem=mensagem, link=link)


# --- estudante ---------------------------------------------------------------

@perfil_requerido(PERFIL_ESTUDANTE)
def meu_progresso(request):
    tema = _temas_aprovados().filter(estudante=request.user).first()
    plano = _plano_de(tema) if tema else None
    return render(request, "progresso/estudante.html", {
        "tema": tema,
        "plano": plano,
        "etapas": list(plano.etapas.all()) if plano else [],
        "info": resumo(plano),
        "hoje": timezone.localdate(),
    })


@perfil_requerido(PERFIL_ESTUDANTE)
@require_POST
def entregar_etapa(request, etapa_id):
    etapa = get_object_or_404(
        EtapaTrabalho.objects.select_related("plano__tema__tutor_indicado"),
        pk=etapa_id, plano__tema__estudante=request.user,
    )
    if not etapa.por_entregar:
        messages.error(request, "Esta etapa já foi entregue.")
        return redirect("meu_progresso")

    ficheiro = request.FILES.get("ficheiro")
    if not ficheiro:
        messages.error(request, "Anexe o ficheiro da entrega.")
        return redirect("meu_progresso")
    if not ficheiro.name.lower().endswith(EXTENSOES_ENTREGA):
        messages.error(request, "Formato não aceite. Use PDF, Word, ODT, PPTX ou ZIP/RAR.")
        return redirect("meu_progresso")
    if ficheiro.size > TAMANHO_MAX_ENTREGA:
        messages.error(request, "O ficheiro excede 20 MB.")
        return redirect("meu_progresso")

    etapa.ficheiro = ficheiro
    etapa.comentario_estudante = request.POST.get("comentario", "").strip()[:2000]
    etapa.estado = "entregue"
    etapa.entregue_em = timezone.now()
    etapa.save()

    tema = etapa.plano.tema
    _avisar(tema.tutor_indicado, "Nova entrega de etapa",
            f"{request.user.nome} {request.user.sobrenome} entregou «{etapa.titulo}».",
            reverse("progresso_tema", args=[tema.pk]))
    messages.success(request, f"«{etapa.titulo}» entregue. O tutor foi notificado.")
    return redirect("meu_progresso")


# --- tutor ---------------------------------------------------------------------

@perfil_requerido(PERFIL_TUTOR)
def progresso_tutor(request):
    linhas = _linhas(_temas_aprovados().filter(tutor_indicado=request.user))
    return render(request, "progresso/tutor.html", {"linhas": linhas, "contagem": _contagem(linhas)})


def _tema_acessivel(request, tema_id):
    """Devolve (tema, pode_editar). Só o orientador edita; a gestão apenas consulta."""
    tema = get_object_or_404(_temas_aprovados(), pk=tema_id)
    user = request.user
    if user.perfil == PERFIL_TUTOR and tema.tutor_indicado_id == user.pk:
        return tema, True
    if tem_perfil(user, *PERFIS_GESTAO):
        if not user.is_superuser and user.perfil == "cordenacao" and user.curso_id and tema.estudante.curso_id != user.curso_id:
            raise PermissionDenied("Este estudante não pertence ao seu curso.")
        return tema, False
    raise PermissionDenied("Não tem permissão para ver este trabalho.")


@perfil_requerido(PERFIL_TUTOR, *PERFIS_GESTAO)
def progresso_tema(request, tema_id):
    tema, pode_editar = _tema_acessivel(request, tema_id)
    plano = _plano_de(tema)
    hoje = timezone.localdate()
    return render(request, "progresso/tema.html", {
        "tema": tema,
        "plano": plano,
        "etapas": list(plano.etapas.all()) if plano else [],
        "info": resumo(plano),
        "pode_editar": pode_editar,
        "base": "tutor/base.html" if request.user.perfil == PERFIL_TUTOR else "admin/base.html",
        "padrao": PLANO_PADRAO,
        "hoje": hoje,
        "prazo_sugerido": hoje + timedelta(days=120),
    })


def _tema_do_orientador(request, tema_id):
    tema, pode_editar = _tema_acessivel(request, tema_id)
    if not pode_editar:
        raise PermissionDenied("Só o tutor orientador pode alterar as etapas.")
    return tema


@perfil_requerido(PERFIL_TUTOR)
@require_POST
def criar_plano(request, tema_id):
    tema = _tema_do_orientador(request, tema_id)
    hoje = timezone.localdate()
    prazo_final = _data(request.POST.get("prazo_final"))
    if not prazo_final or prazo_final <= hoje:
        messages.error(request, "Indique uma data final posterior a hoje.")
        return redirect("progresso_tema", tema.pk)

    with transaction.atomic():
        plano, _ = PlanoTrabalho.objects.get_or_create(tema=tema)
        if plano.etapas.exists():
            messages.error(request, "Este trabalho já tem etapas definidas.")
            return redirect("progresso_tema", tema.pk)
        # prazos distribuídos de forma igual até à data final
        passo = (prazo_final - hoje) / len(PLANO_PADRAO)
        for i, (titulo, descricao) in enumerate(PLANO_PADRAO, start=1):
            prazo = prazo_final if i == len(PLANO_PADRAO) else hoje + passo * i
            EtapaTrabalho.objects.create(plano=plano, ordem=i, titulo=titulo, descricao=descricao, prazo=prazo)

    _avisar(tema.estudante, "Plano de trabalho definido",
            f"O seu tutor definiu {len(PLANO_PADRAO)} etapas para o TFC. A primeira termina em breve; consulte os prazos.",
            reverse("meu_progresso"))
    messages.success(request, "Plano criado com 5 etapas. Ajuste os prazos e títulos se precisar.")
    return redirect("progresso_tema", tema.pk)


@perfil_requerido(PERFIL_TUTOR)
@require_POST
def guardar_etapa(request, tema_id, etapa_id=None):
    tema = _tema_do_orientador(request, tema_id)
    titulo = request.POST.get("titulo", "").strip()[:150]
    prazo = _data(request.POST.get("prazo"))
    if not titulo or not prazo:
        messages.error(request, "Indique o título e o prazo da etapa.")
        return redirect("progresso_tema", tema.pk)

    plano, _ = PlanoTrabalho.objects.get_or_create(tema=tema)
    if etapa_id:
        etapa = get_object_or_404(EtapaTrabalho, pk=etapa_id, plano=plano)
        if etapa.prazo != prazo:
            # prazo novo: os avisos voltam a poder ser enviados
            etapa.alerta_prazo_enviado = etapa.alerta_atraso_enviado = False
    else:
        ultima = plano.etapas.aggregate(m=Max("ordem"))["m"] or 0
        etapa = EtapaTrabalho(plano=plano, ordem=ultima + 1)
    etapa.titulo = titulo
    etapa.descricao = request.POST.get("descricao", "").strip()[:2000]
    etapa.prazo = prazo
    etapa.save()
    messages.success(request, "Etapa guardada." if etapa_id else "Etapa adicionada.")
    return redirect("progresso_tema", tema.pk)


@perfil_requerido(PERFIL_TUTOR)
@require_POST
def eliminar_etapa(request, tema_id, etapa_id):
    tema = _tema_do_orientador(request, tema_id)
    etapa = get_object_or_404(EtapaTrabalho, pk=etapa_id, plano__tema=tema)
    if etapa.estado != "pendente":
        messages.error(request, "Não pode eliminar uma etapa que já teve entregas.")
    else:
        etapa.delete()
        messages.success(request, "Etapa eliminada.")
    return redirect("progresso_tema", tema.pk)


@perfil_requerido(PERFIL_TUTOR)
@require_POST
def avaliar_etapa(request, tema_id, etapa_id):
    tema = _tema_do_orientador(request, tema_id)
    etapa = get_object_or_404(EtapaTrabalho, pk=etapa_id, plano__tema=tema)
    decisao = request.POST.get("decisao")
    comentario = request.POST.get("comentario", "").strip()[:2000]

    if etapa.estado != "entregue":
        messages.error(request, "Só pode avaliar etapas entregues.")
        return redirect("progresso_tema", tema.pk)
    if decisao == "revisao" and not comentario:
        messages.error(request, "Explique ao estudante o que deve corrigir.")
        return redirect("progresso_tema", tema.pk)
    if decisao not in ("aprovada", "revisao"):
        messages.error(request, "Decisão inválida.")
        return redirect("progresso_tema", tema.pk)

    etapa.estado = decisao
    etapa.comentario_tutor = comentario
    etapa.avaliada_em = timezone.now()
    etapa.save(update_fields=["estado", "comentario_tutor", "avaliada_em"])

    if decisao == "aprovada":
        _avisar(tema.estudante, "Etapa aprovada", f"O tutor aprovou «{etapa.titulo}».", reverse("meu_progresso"))
        messages.success(request, f"«{etapa.titulo}» aprovada.")
    else:
        _avisar(tema.estudante, "Etapa a rever", f"O tutor pediu correções em «{etapa.titulo}»: {comentario[:200]}", reverse("meu_progresso"))
        messages.success(request, "Pedido de revisão enviado ao estudante.")
    return redirect("progresso_tema", tema.pk)


# --- coordenação e restantes perfis de gestão ---------------------------------

@perfil_requerido(*PERFIS_GESTAO)
def progresso_geral(request):
    user = request.user
    temas = _temas_aprovados()
    if not user.is_superuser and user.perfil == "cordenacao" and user.curso_id:
        temas = temas.filter(estudante__curso_id=user.curso_id)

    linhas = _linhas(temas)
    contagem = _contagem(linhas)
    filtro = request.GET.get("estado", "")
    if filtro in contagem:
        linhas = [l for l in linhas if l["info"]["estado"] == filtro]
    return render(request, "progresso/geral.html", {"linhas": linhas, "contagem": contagem, "filtro": filtro})
