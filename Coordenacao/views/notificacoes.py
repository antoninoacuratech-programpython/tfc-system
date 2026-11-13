"""Notificações do sistema."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Notificacao, NotificacaoFinal


@login_required
def ver_notificacao(request, notif_id):
    notif = get_object_or_404(Notificacao, id=notif_id, usuario=request.user)
    notif.lida = True
    notif.save()
    # redireciona direto para baixar o PDF do comunicado
    return redirect('baixar_comunicado_pdf', id=notif.comunicado.id)


@login_required
def listar_notificacoes(request):
    # Lógica de seleção de template base baseada no perfil
    perfil = getattr(request.user, 'perfil', None)
    
    if perfil == 'estudante':
        base_template = 'Estudante/base.html'
    elif perfil == 'tutor':
        base_template = 'tutor/base.html'  # Certifique-se de ter este arquivo
    else:
        base_template = 'admin/base.html'

    # Busca as notificações ordenadas pela mais recente
    todas_notificacoes = NotificacaoFinal.objects.filter(usuario=request.user).order_by('-criada_em')
    
    # Calcula o contador de não lidas para o template
    notificacoes_nao_lidas_count = todas_notificacoes.filter(lida=False).count()

    context = {
        'base_template': base_template,
        'todas_notificacoes': todas_notificacoes,
        'notificacoes_nao_lidas_count': notificacoes_nao_lidas_count
    }
    
    return render(request, 'notificacoes.html', context)


@login_required
def marcar_notificacao_lida(request, pk):
    """
    Marca uma notificação como lida e redireciona para o link associado, 
    se existir. Caso contrário, retorna à lista de notificações.
    """
    notificacao = get_object_or_404(NotificacaoFinal, id=pk, usuario=request.user)
    
    # Marca como lida
    notificacao.lida = True
    notificacao.save()
    
    # Se existir um link, redireciona para ele, caso contrário, volta para a lista
    if notificacao.link:
        return redirect(notificacao.link)
    
    return redirect('listar_notificacoes')
