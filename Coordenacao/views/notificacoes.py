"""Notificações do sistema."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Notificacao, NotificacaoFinal


@login_required
def ver_notificacao(request, notif_id):
    notif = get_object_or_404(Notificacao, id=notif_id, usuario=request.user)
    notif.lida = True
    notif.save()
    return redirect('baixar_comunicado_pdf', id=notif.comunicado.id)


@login_required
def listar_notificacoes(request):
    perfil = getattr(request.user, 'perfil', None)
    
    if perfil == 'estudante':
        base_template = 'Estudante/base.html'
    elif perfil == 'tutor':
        base_template = 'tutor/base.html'
    else:
        base_template = 'admin/base.html'

    todas_notificacoes = NotificacaoFinal.objects.filter(usuario=request.user).order_by('-criada_em')
    
    notificacoes_nao_lidas_count = todas_notificacoes.filter(lida=False).count()

    context = {
        'base_template': base_template,
        'todas_notificacoes': todas_notificacoes,
        'notificacoes_nao_lidas_count': notificacoes_nao_lidas_count
    }
    
    return render(request, 'notificacoes.html', context)


@login_required
def marcar_notificacao_lida(request, pk):
    notificacao = get_object_or_404(NotificacaoFinal, id=pk, usuario=request.user)
    
    notificacao.lida = True
    notificacao.save()
    
    if notificacao.link:
        return redirect(notificacao.link)
    
    return redirect('listar_notificacoes')
