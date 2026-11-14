"""Temas sugeridos pela coordenação e escolhidos pelos estudantes."""

from django.contrib import messages
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import Curso, NotificacaoFinal, ProcessoEtapa, Tema, TemaSugerido, tutores
from ..permissions import PERFIL_COORDENACAO, PERFIL_ESTUDANTE, perfil_requerido


def _sugestoes_visiveis(user):
    qs = TemaSugerido.objects.select_related("curso", "tutor_sugerido", "tema__estudante")
    if user.is_superuser or not user.curso_id:
        return qs
    return qs.filter(curso_id=user.curso_id)


def _cursos_permitidos(user):
    if user.is_superuser or not user.curso_id:
        return Curso.objects.order_by("nome")
    return Curso.objects.filter(pk=user.curso_id)


def _guardar(request, sugestao):
    titulo = request.POST.get("titulo", "").strip()
    descricao = request.POST.get("descricao", "").strip()
    curso = _cursos_permitidos(request.user).filter(pk=request.POST.get("curso")).first()
    tutor_id = request.POST.get("tutor_sugerido") or None
    tutor = tutores().filter(pk=tutor_id).first() if tutor_id else None

    if not titulo or not descricao or not curso:
        messages.error(request, "Preencha o título, a descrição e o curso.")
        return False
    if tutor_id and not tutor:
        messages.error(request, "Tutor inválido.")
        return False

    sugestao.titulo, sugestao.descricao, sugestao.curso, sugestao.tutor_sugerido = titulo, descricao, curso, tutor
    if not sugestao.pk:
        sugestao.criado_por = request.user
    sugestao.save()
    return True


@perfil_requerido(PERFIL_COORDENACAO)
def gerir_sugestoes(request):
    if request.method == "POST":
        if _guardar(request, TemaSugerido()):
            messages.success(request, "Tema sugerido publicado. Os estudantes do curso já o podem ver.")
        return redirect("gerir_sugestoes")

    sugestoes = list(_sugestoes_visiveis(request.user))
    return render(request, "sugestoes/gerir.html", {
        "sugestoes": sugestoes,
        "cursos": _cursos_permitidos(request.user),
        "tutores": tutores().filter(estado_user="activo").order_by("nome"),
        "total_abertas": sum(1 for s in sugestoes if s.disponivel),
        "total_escolhidas": sum(1 for s in sugestoes if s.escolhido),
    })


@perfil_requerido(PERFIL_COORDENACAO)
def editar_sugestao(request, pk):
    sugestao = get_object_or_404(_sugestoes_visiveis(request.user), pk=pk)
    if request.method == "POST":
        if _guardar(request, sugestao):
            messages.success(request, "Tema sugerido actualizado.")
            return redirect("gerir_sugestoes")
    return render(request, "sugestoes/editar.html", {
        "s": sugestao,
        "cursos": _cursos_permitidos(request.user),
        "tutores": tutores().filter(estado_user="activo").order_by("nome"),
    })


@perfil_requerido(PERFIL_COORDENACAO)
@require_POST
def alternar_sugestao(request, pk):
    sugestao = get_object_or_404(_sugestoes_visiveis(request.user), pk=pk)
    sugestao.estado = "fechado" if sugestao.estado == "aberto" else "aberto"
    sugestao.save(update_fields=["estado"])
    messages.success(request, "Sugestão reaberta." if sugestao.estado == "aberto" else "Sugestão fechada; deixa de aparecer aos estudantes.")
    return redirect("gerir_sugestoes")


@perfil_requerido(PERFIL_COORDENACAO)
@require_POST
def eliminar_sugestao(request, pk):
    sugestao = get_object_or_404(_sugestoes_visiveis(request.user), pk=pk)
    if sugestao.escolhido:
        messages.error(request, "Este tema já foi escolhido por um estudante. Pode fechá-lo, mas não eliminá-lo.")
    else:
        sugestao.delete()
        messages.success(request, "Tema sugerido eliminado.")
    return redirect("gerir_sugestoes")


def _processo_aberto(curso):
    hoje = timezone.now().date()
    return ProcessoEtapa.objects.filter(curso=curso, ativo=True, data_inicio__lte=hoje, data_termino__gte=hoje).first()


@perfil_requerido(PERFIL_ESTUDANTE)
def sugestoes_estudante(request):
    user = request.user
    sugestoes = TemaSugerido.objects.select_related("tutor_sugerido", "tema").filter(estado="aberto")
    sugestoes = [s for s in sugestoes.filter(curso_id=user.curso_id) if not s.escolhido] if user.curso_id else []
    tema_atual = Tema.objects.filter(estudante=user).first()
    return render(request, "sugestoes/estudante.html", {
        "sugestoes": sugestoes,
        "tutores": tutores().filter(estado_user="activo").order_by("nome"),
        "tema_atual": tema_atual,
        "pode_escolher": not tema_atual or tema_atual.status_coordenacao == "rejeitado",
        "processo": _processo_aberto(user.curso) if user.curso_id else None,
    })


@perfil_requerido(PERFIL_ESTUDANTE)
@require_POST
def escolher_sugestao(request, pk):
    user = request.user
    processo = _processo_aberto(user.curso) if user.curso_id else None
    if not processo:
        messages.error(request, "O período de submissão de temas do seu curso não está aberto.")
        return redirect("sugestoes_estudante")

    tutor = tutores().filter(pk=request.POST.get("tutor_indicado") or 0).first()
    if not tutor:
        messages.error(request, "Escolha o tutor que vai orientar o trabalho.")
        return redirect("sugestoes_estudante")

    with transaction.atomic():
        sugestao = get_object_or_404(
            # of=("self",): o PostgreSQL não deixa bloquear o lado opcional do join
            TemaSugerido.objects.select_for_update(of=("self",)).select_related("tema"),
            pk=pk, curso_id=user.curso_id, estado="aberto",
        )
        if sugestao.escolhido:
            messages.error(request, "Este tema acabou de ser escolhido por outro estudante.")
            return redirect("sugestoes_estudante")

        tema = Tema.objects.filter(estudante=user).first()
        if tema and tema.status_coordenacao != "rejeitado":
            messages.error(request, "Já tem um tema em avaliação. Só pode escolher outro se o actual for rejeitado.")
            return redirect("sugestoes_estudante")

        if tema:
            # a sugestão antiga (se havia) volta a ficar livre
            TemaSugerido.objects.filter(tema=tema).update(tema=None)
        else:
            tema = Tema(estudante=user)
        tema.titulo = sugestao.titulo
        tema.descricao = sugestao.descricao
        tema.tutor_indicado = tutor
        tema.processo = processo
        tema.status_tutor = "pendente"
        tema.status_coordenacao = "pendente"
        if request.FILES.get("resumo"):
            tema.resumo = request.FILES["resumo"]
        if request.FILES.get("requerimento"):
            tema.requerimento = request.FILES["requerimento"]
        tema.save()

        sugestao.tema = tema
        sugestao.save(update_fields=["tema"])

    if sugestao.criado_por_id:
        NotificacaoFinal.objects.create(
            usuario_id=sugestao.criado_por_id,
            titulo="Tema sugerido escolhido",
            mensagem=f"{user.nome} {user.sobrenome} escolheu o tema \"{sugestao.titulo}\" com o tutor {tutor.nome} {tutor.sobrenome}.",
            link=reverse("gerir_sugestoes"),
        )
    messages.success(request, "Tema escolhido! A proposta foi enviada ao tutor para avaliação.")
    return redirect("dashboard_estudante")
