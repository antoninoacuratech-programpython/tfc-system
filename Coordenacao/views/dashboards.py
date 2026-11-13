"""Painéis iniciais de cada perfil."""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import redirect, render

from ..models import (
    Comunicado,
    Despacho,
    InscricaoTFC,
    NotificacaoTFC,
    Predefesa,
    Recomendacao,
    Tema,
    Usuario,
)
from ..permissions import PERFIS_GESTAO, perfil_requerido

User = get_user_model()


@login_required
def index_area_etica(request):
    if request.user.perfil != "area_etica" and not request.user.is_superuser:
        return HttpResponseForbidden("Você não tem permissão para acessar a Área Ética.")

    context = {
        'total_avaliacoes': 124,  
        'pendentes_count': 12,    
        'alertas_count': 3,       
        
        'estudantes_avaliar': [], 
    }
    
    return render(request, 'Area_etica/area_etica.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def admink(request):
    comunicados = Comunicado.objects.all().order_by('-data_publicacao')
    total_comunicados = comunicados.count()
    inscricoes_pendentes_count = InscricaoTFC.objects.filter(status='pendente').count()
    total_predefesas = Predefesa.objects.count()
    total_despachos = Despacho.objects.count()

    if request.user.perfil == 'cordenacao' and request.user.curso:
        usuarios_qs = User.objects.filter(perfil='estudante', curso=request.user.curso)
    elif request.user.is_superuser:
        usuarios_qs = User.objects.exclude(perfil='estudante')
    else:
        usuarios_qs = User.objects.filter(perfil='estudante')

    tutores = User.objects.filter(perfil='tutor')
    lista_temas_reprovados = Tema.objects.exclude(status_final='aprovado')

    return render(request, 'admin/index.html', {
        'total': usuarios_qs.count(),
        'total_tutor': tutores.count(),
        'nome': request.user.nome,
        'tutores': tutores,
        'total_temas': lista_temas_reprovados.count(),
        'comunicados': comunicados,
        'total_comunicados': total_comunicados
    })


@login_required
def dashboard_estudante(request):
    user = request.user
    temas = Tema.objects.filter(estudante=user).order_by('-data_envio')
    
    total_tutor = User.objects.filter(perfil='tutor').count()
    total_estudantes = User.objects.filter(perfil='estudante').count()

    total_notificacoes_tfc = NotificacaoTFC.objects.filter(
        destinatario=user, 
        lida=False
    ).count()

    recomendacoes_nao_lidas = Recomendacao.objects.filter(tema__estudante=user, lida=False)
    total_recomendacoes = recomendacoes_nao_lidas.count()
    recomendacoes_nao_lidas.update(lida=True)

    return render(request, 'Estudante/index.html', {
        'total': total_estudantes,
        'total_tutor': total_tutor,
        'nome': user.nome,
        'total_recomendacoes': total_recomendacoes,
        'total_notificacoes_tfc': total_notificacoes_tfc, 
        'tutores': User.objects.filter(perfil='tutor'),
        'temas': temas
    })


@login_required
def dashboard_tutor(request):
    if request.user.perfil != 'tutor':
        messages.error(request, "Acesso negado.")
        return redirect('login')

    temas = Tema.objects.filter(tutor_indicado=request.user).order_by('-data_envio')

    return render(request, "tutor/index.html", {
        "temas": temas
    })


@perfil_requerido(*PERFIS_GESTAO)
def dashboard_presidencia(request):
    total_estudantes = Usuario.objects.filter(perfil="estudante").count()
    total_temas = Tema.objects.count()
    total_recomendacoes = Recomendacao.objects.count()

    ultimos_temas = Tema.objects.order_by('-id')[:5]

    context = {
        'total_estudantes': total_estudantes,
        'total_temas': total_temas,
        'total_recomendacoes': total_recomendacoes,
        'temas': ultimos_temas,
    }
    return render(request, 'admin/presidente.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def index_area_cientifica(request):
    try:
        comunicados = Comunicado.objects.all().order_by('-data_publicacao')
        total_comunicados = comunicados.count()
        
        inscricoes_pendentes_count = InscricaoTFC.objects.filter(status='pendente').count()

        total_predefesas = Predefesa.objects.count()

        total_despachos = Despacho.objects.count()

        despachos_aguardando_assinatura = Despacho.objects.filter(status='pendente').count()

        despachos_para_publicar = Despacho.objects.filter(status='aprovado', publicado=False).count()

        temas_para_validar_count = Tema.objects.filter(
            listas_aprovadas__status='enviado'
        ).distinct().count()

    except Exception as e:
        print(f"Erro na view index_area_cientifica: {e}")
        inscricoes_pendentes_count = 0
        total_predefesas = 0
        total_despachos = 0
        despachos_aguardando_assinatura = 0
        despachos_para_publicar = 0
        comunicados = []
        total_comunicados = 0
        temas_para_validar_count = 0
    
    context = {
        'comunicados': comunicados,
        'total_comunicados': total_comunicados,
        'inscricoes_pendentes_count': inscricoes_pendentes_count,
        'total_predefesas': total_predefesas,
        'total_despachos': total_despachos,
        'despachos_pendentes': despachos_aguardando_assinatura,
        'despachos_prontos': despachos_para_publicar,
        'temas_para_validar_count': temas_para_validar_count,
    }
    
    return render(request, 'Area_Cientifica/area_cientifica.html', context)
