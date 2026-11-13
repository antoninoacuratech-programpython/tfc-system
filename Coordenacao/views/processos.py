"""Processos (etapas do calendário) e calendários de aprovação."""

from datetime import datetime

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ..models import CalendarioAprovacao, Curso, ProcessoEtapa
from ..permissions import PERFIS_GESTAO, perfil_requerido


@perfil_requerido(*PERFIS_GESTAO)
def lista_processos(request):
    processos = ProcessoEtapa.objects.filter(curso=request.user.curso).order_by('-criado_em')
    cursos = Curso.objects.all() 
    
    return render(request, 'processos/lista.html', {
        'processos': processos,
        'cursos': cursos,
        'hoje': timezone.now().date()
    })


@perfil_requerido(*PERFIS_GESTAO)
@require_POST
def criar_processo(request):
    if request.method == "POST":
        titulo = request.POST.get('titulo')
        data_inicio = request.POST.get('data_inicio')
        data_termino = request.POST.get('data_termino')
        curso_id = request.POST.get('curso')

        if data_termino < data_inicio:
            messages.error(request, "A data de término não pode ser menor que a de início.")
            return redirect('lista_processos')

        try:
            ProcessoEtapa.objects.create(
                titulo=titulo,
                data_inicio=data_inicio,
                data_termino=data_termino,
                curso_id=curso_id,
                coordenador=request.user,
                ativo=True
            )
            messages.success(request, "Processo de TFC aberto com sucesso!")
        except Exception as e:
            messages.error(request, f"Erro ao criar processo: {e}")
            
        return redirect('lista_processos')


@perfil_requerido(*PERFIS_GESTAO)
def alternar_status_processo(request, pk):
    processo = get_object_or_404(ProcessoEtapa, pk=pk)
    processo.ativo = not processo.ativo
    processo.save()
    messages.info(request, f"Status do processo '{processo.titulo}' atualizado.")
    return redirect('lista_processos')


@perfil_requerido(*PERFIS_GESTAO)
@require_POST
def editar_processo(request, pk):
    processo = get_object_or_404(ProcessoEtapa, pk=pk)
    titulo = request.POST.get('titulo')
    curso_id = request.POST.get('curso')
    data_inicio = request.POST.get('data_inicio')
    data_termino = request.POST.get('data_termino')
    
    try:
        processo.titulo = titulo
        if curso_id:
            processo.curso_id = curso_id
        processo.data_inicio = data_inicio
        processo.data_termino = data_termino
        processo.save()
        messages.success(request, f"O processo '{titulo}' foi atualizado com sucesso!")
    except Exception as e:
        messages.error(request, f"Erro ao atualizar o processo: {str(e)}")
        
    return redirect(request.META.get('HTTP_REFERER', 'lista_processos'))


@perfil_requerido(*PERFIS_GESTAO)
@require_POST
def eliminar_processo(request, pk):
    processo = get_object_or_404(ProcessoEtapa, pk=pk)
    titulo = processo.titulo
    try:
        processo.delete()
        messages.success(request, f"O processo '{titulo}' foi eliminado definitivamente.")
    except Exception as e:
        messages.error(request, f"Não foi possível eliminar o processo: {str(e)}")
        
    return redirect(request.META.get('HTTP_REFERER', 'lista_processos'))


@perfil_requerido(*PERFIS_GESTAO)
def gerir_calendarios(request):
    if request.method == 'POST' and 'criar' in request.POST:
        data_input = request.POST.get('data_aprovacao')
        try:
            data_formatada = datetime.fromisoformat(data_input)
        except (ValueError, TypeError):
            messages.error(request, "Erro ao processar a data. Tente novamente.")
            return redirect('gerir_calendarios')

        CalendarioAprovacao.objects.create(
            titulo=request.POST.get('titulo'),
            data_aprovacao=data_formatada,
            periodo=request.POST.get('periodo'),
            curso_id=request.POST.get('curso_id'),
            ativo=True
        )
        messages.success(request, "Calendário criado e estudantes notificados!")
        return redirect('gerir_calendarios')

    if request.method == 'POST' and 'excluir' in request.POST:
        calendario_id = request.POST.get('calendario_id')
        calendario = get_object_or_404(CalendarioAprovacao, id=calendario_id)
        calendario.delete()
        messages.warning(request, "Calendário removido com sucesso.")
        return redirect('gerir_calendarios')

    context = {
        'calendarios': CalendarioAprovacao.objects.all().order_by('-data_aprovacao'),
        'cursos': Curso.objects.all()
    }
    return render(request, 'admin/calendarios.html', context)
