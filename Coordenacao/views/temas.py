"""Submissão, avaliação e exportação de temas de TFC."""

import io
import os
from itertools import groupby

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import ListaTemasAprovados, ProcessoEtapa, Tema, Usuario
from ..similaridade import temas_semelhantes
from ..permissions import PERFIL_COORDENACAO, PERFIL_TUTOR, PERFIS_GESTAO, perfil_requerido


@perfil_requerido(*PERFIS_GESTAO)
def lista_estudantes(request, processo_id=None):
    user = request.user
    if request.method == "POST":
        ids_selecionados = request.POST.getlist('usuarios')
        acao = request.POST.get('acao')

        if ids_selecionados:
            queryset_update = Usuario.objects.filter(id__in=ids_selecionados, perfil='estudante')
            
            if user.perfil == 'cordenacao':
                queryset_update = Usuario.objects.filter(id__in=ids_selecionados, perfil='estudante')
                queryset_update = queryset_update.filter(curso=user.curso)

            if request.user.is_staff:
                queryset_update = Usuario.objects.filter(id__in=ids_selecionados)

            if acao == 'activar':
                queryset_update.update(estado_user='activo')
                messages.success(request, f"{queryset_update.count()} estudante(s) ativado(s) com sucesso.")
            elif acao == 'desativar':
                queryset_update.update(estado_user='desativado')
                messages.success(request, f"{queryset_update.count()} estudante(s) desativado(s) com sucesso.")
        
        return redirect(request.get_full_path())

    estudantes_qs = Usuario.objects.filter(perfil='estudante')
    if user.perfil == 'cordenacao':
        estudantes_qs = estudantes_qs.filter(curso=user.curso)

    processo_nome = "Todos os Processos"
    
    if processo_id:
        if user.perfil == 'cordenacao':
            processo = get_object_or_404(ProcessoEtapa, id=processo_id, curso=user.curso)
        else:
            processo = get_object_or_404(ProcessoEtapa, id=processo_id)
        
        estudantes_qs = estudantes_qs.filter(temas__processo=processo).distinct()
        processo_nome = processo.titulo

    temas_prefetch = Prefetch(
        'temas',
        queryset=Tema.objects.all().select_related('processo', 'tutor_indicado'),
        to_attr='tema_list'
    )
    
    estudantes = estudantes_qs.prefetch_related(temas_prefetch).order_by('nome').distinct()
    if processo_id:
        if request.user.is_staff:
            estudantes = Usuario.objects.all()

    context = {
        "estudantes": estudantes,
        "processo_selecionado": processo_id,
        "processo_nome_exibicao": processo_nome,
        "processos_disponiveis": ProcessoEtapa.objects.filter(curso=user.curso) if user.perfil == 'cordenacao' else ProcessoEtapa.objects.all(),
    }

    return render(request, "admin/lista_estudantes.html", context)


@login_required
def alterar_status_tema(request, tema_id, novo_status):
    if request.user.perfil not in ['tutor', 'cordenacao']:
        messages.error(request, "Acesso negado.")
        return redirect('lista_estudantes')

    tema = get_object_or_404(Tema, id=tema_id)

    if novo_status not in ['aprovado', 'rejeitado', 'pendente']:
        messages.error(request, "Status inválido.")
        if request.user.perfil == 'tutor':
            return redirect('dashboard_tutor')
        return redirect('lista_reprovados') 

    if request.user.perfil == 'tutor':
        tema.status_tutor = novo_status
        tema.save()
        messages.success(request, f"Status do tutor atualizado para: {novo_status}")
        return redirect('lista_estudantes') 

    if request.user.perfil == 'cordenacao':
        
        tema.status_coordenacao = novo_status
        tema.save()
        
        if novo_status == 'aprovado':
            messages.success(request, f"Status da coordenação atualizado para: {novo_status}")
        else:
            messages.error(request, f"Status da coordenação atualizado para: {novo_status}")
            
        return redirect('lista_reprovados')


def get_temas_filtrados(user, status_aprovado=True):
    if status_aprovado:
        queryset = Tema.objects.filter(status_final='aprovado')
    else:
        queryset = Tema.objects.exclude(status_final='aprovado')
    queryset = queryset.select_related('estudante', 'tutor_indicado', 'estudante__curso')
    if user.perfil == 'cordenacao' and user.curso:
        queryset = queryset.filter(estudante__curso=user.curso)
        
    return queryset


@perfil_requerido(*PERFIS_GESTAO)
def temas_aprovados(request):
    temas = get_temas_filtrados(request.user, status_aprovado=True)
    return render(request, "admin/lista_aprovados.html", {"lista_temas_aprovados": temas})


@perfil_requerido(*PERFIS_GESTAO)
def temas_reprovados(request):
    temas = get_temas_filtrados(request.user, status_aprovado=False)
    return render(request, "admin/lista_reprovados.html", {"lista_temas_aprovados": temas})


@perfil_requerido(*PERFIS_GESTAO)
def alterar_status_multiplos(request):
    if request.method != "POST":
        return redirect("lista_reprovados")

    ids = request.POST.getlist("temas_selecionados")
    acao = request.POST.get("acao")

    if not ids:
        messages.error(request, "Nenhum tema selecionado.")
        return redirect("lista_reprovados")

    temas = Tema.objects.filter(id__in=ids)

    if acao == "aprovar":
        nao_aprovados = temas.exclude(status_tutor="aprovado")

        if nao_aprovados.exists():
            messages.error(request, "Aguarde a aprovação do tutor para alguns temas selecionados.")
            return redirect("lista_reprovados")

        temas.update(status_coordenacao="aprovado")
        messages.success(request, f"{len(temas)} tema(s) aprovado(s) pela coordenação.")
        return redirect("lista_reprovados")

    elif acao == "rejeitar":
        temas.update(status_coordenacao="rejeitado")
        messages.error(request, f"{len(temas)} tema(s) rejeitado(s) pela coordenação.")
        return redirect("lista_reprovados")

    messages.error(request, "Ação inválida.")
    return redirect("lista_reprovados")


@login_required
def criar_ou_editar_tema(request):
    if request.method != "POST":
        return redirect("dashboard_estudante")
    
    hoje = timezone.now().date()
    if not request.user.curso:
        messages.error(request, "Você precisa estar vinculado a um curso para submeter temas.")
        return redirect("dashboard_estudante")

    processo = ProcessoEtapa.objects.filter(
        curso=request.user.curso,
        ativo=True,
        data_inicio__lte=hoje,
        data_termino__gte=hoje
    ).first()

    if not processo:
        messages.error(request, f"O período de submissão de temas para o curso {request.user.curso.nome} está fechado ou não foi iniciado.")
        return redirect("dashboard_estudante")

    titulo = request.POST.get('titulo')
    descricao = request.POST.get('descricao')
    resumo = request.FILES.get('resumo')
    requerimento = request.FILES.get('requerimento')
    tutor_id = request.POST.get('tutor_indicado')

    if not titulo or not descricao or not tutor_id:
        messages.error(request, "Por favor, preencha todos os campos obrigatórios.")
        return redirect("dashboard_estudante")

    try:
        tutor = Usuario.objects.get(id=tutor_id, perfil='tutor')
    except Usuario.DoesNotExist:
        messages.error(request, "Tutor selecionado inválido.")
        return redirect("dashboard_estudante")

    tema_existente = Tema.objects.filter(estudante=request.user).first()

    try:
        if tema_existente:
            if tema_existente.status_coordenacao != "rejeitado":
                messages.error(request, "Não é possível modificar o tema enquanto ele não for rejeitado pela coordenação.")
                return redirect("dashboard_estudante")

            tema_existente.titulo = titulo
            tema_existente.descricao = descricao
            if resumo:
                tema_existente.resumo = resumo
            if requerimento:
                tema_existente.requerimento = requerimento
            
            tema_existente.tutor_indicado = tutor
            tema_existente.processo = processo
            tema_existente.status_tutor = 'pendente'
            tema_existente.status_coordenacao = 'pendente'
            tema_existente.save()
            
            messages.success(request, "Tema atualizado com sucesso e enviado para nova aprovação.")
        
        else:
            Tema.objects.create(
                estudante=request.user,
                titulo=titulo,
                descricao=descricao,
                resumo=resumo,
                requerimento=requerimento,
                tutor_indicado=tutor,
                processo=processo,
                status_tutor='pendente',
                status_coordenacao='pendente',
            )
            messages.success(request, "Tema enviado com sucesso.")

    except Exception as e:
        messages.error(request, f"Erro ao processar: {e}")
    else:
        parecidos = temas_semelhantes(titulo, descricao, excluir_estudante_id=request.user.pk, limite=1, minimo=0.75)
        if parecidos:
            p = parecidos[0]
            messages.warning(request, f"Atenção: o seu tema é {p['percentagem']}% parecido com «{p['titulo']}» ({p['autor']}). O tutor e a coordenação vão ter isso em conta.")

    return redirect("dashboard_estudante")


@login_required
def alterar_status_tema_tutor(request, tema_id, novo_status):
    if request.user.perfil not in ['tutor', 'cordenacao']: 
        messages.error(request, "Acesso negado.")
        return redirect('dashboard_tutor')

    tema = get_object_or_404(Tema, id=tema_id)
    if request.user.perfil == 'tutor' and tema.tutor_indicado != request.user:
        messages.error(request, "Você não pode alterar status de temas que não são seus.")
        return redirect('dashboard_tutor')

    if novo_status not in ['pendente', 'aprovado', 'rejeitado']:
        messages.error(request, "Status inválido.")
        return redirect('dashboard_tutor')
    tema.status_tutor = novo_status
    tema.save()
    
    if novo_status == 'aprovado':
        messages.success(request, f"Status do tema atualizado para: {novo_status}")
    elif novo_status == 'rejeitado':
        messages.error(request, f"Status do tema atualizado para: {novo_status}")
    else: 
        messages.info(request, f"Status do tema atualizado para: {novo_status}")
        
    return redirect('dashboard_tutor')


@perfil_requerido(PERFIL_TUTOR, PERFIL_COORDENACAO)
def alterar_status_multiplos_tutor(request):
    if request.method != "POST":
        return redirect("dashboard_tutor")

    ids = request.POST.getlist("temas_selecionados")
    acao = request.POST.get("acao")

    if not ids:
        messages.error(request, "Nenhum tema selecionado.")
        return redirect("dashboard_tutor")

    temas = Tema.objects.filter(id__in=ids, tutor_indicado=request.user) 

    if acao == "aprovar":
        temas.update(status_tutor="aprovado")
        messages.success(request, f"{len(temas)} tema(s) aprovado(s).")

    elif acao == "rejeitar":
        temas.update(status_tutor="rejeitado")
        messages.error(request, f"{len(temas)} tema(s) rejeitado(s).")
    
    else:
        messages.error(request, "Ação inválida.")

    return redirect("dashboard_tutor")


@login_required
def lista_todos_temas_geral(request):
    temas = list(
        Tema.objects.select_related('estudante', 'estudante__curso', 'tutor_indicado', 'processo')
        .order_by('estudante__curso__nome', 'titulo')
    )
    processos = list(ProcessoEtapa.objects.all())
    for tema in temas:
        tema.processo_mostrado = tema.processo
        if not tema.processo_mostrado and tema.estudante.curso_id and tema.data_envio:
            # temas antigos não guardavam o processo: deduz-se pela data de envio
            data = timezone.localtime(tema.data_envio).date()
            tema.processo_mostrado = next(
                (p for p in processos if p.curso_id == tema.estudante.curso_id and p.data_inicio <= data <= p.data_termino),
                None,
            )
    return render(request, 'Estudante/lista_geral_temas.html', {'temas': temas})


@login_required
def adicionar_orientador(request, tema_id):
    if request.user.perfil != 'cordenacao':
        messages.error(request, "Acesso negado. Apenas a coordenação pode atribuir orientadores.")
        return redirect('admink')

    tema = get_object_or_404(Tema, id=tema_id)
    tutores = Usuario.objects.filter(perfil='tutor', estado_user='activo')

    if request.method == 'POST':
        tutor_id = request.POST.get('tutor')
        if tutor_id:
            tutor = get_object_or_404(Usuario, id=tutor_id)
            
            tema.tutor_indicado = tutor
            tema.status_tutor = 'aprovado'
            tema.status_coordenacao = 'aprovado'
            tema.save()
            
            messages.success(request, f"Orientador {tutor.nome} atribuído e tema aprovado com sucesso!")
            return redirect('lista_estudantes')
        else:
            messages.error(request, "Por favor, selecione um orientador.")

    return render(request, 'admin/adicionar_orientador.html', {
        'tema': tema,
        'tutores': tutores
    })


def gerar_buffer_listagem_temas():
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=1.5*cm, leftMargin=1.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    
    style_title = ParagraphStyle(name='Title_ISP', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=12, alignment=TA_CENTER)
    style_header_table = ParagraphStyle(name='HeaderTable', fontName='Helvetica-Bold', fontSize=9, leading=10, textColor=colors.whitesmoke)
    style_cell = ParagraphStyle(name='CellTable', fontName='Helvetica', fontSize=8, leading=10)

    relative_path = 'imgs/icons/finalispbie.jpg'
    logo_path = finders.find(relative_path) or os.path.join(settings.STATIC_ROOT, relative_path)
    
    try:
        logo = Image(logo_path, width=2.0*cm, height=2.0*cm)
        elements.append(logo)
    except:
        pass

    elements.append(Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_title))
    elements.append(Paragraph("DEPARTAMENTO DE ENSINO E INVESTIGAÇÃO", style_title))
    elements.append(Spacer(1, 0.5*cm))
    elements.append(Paragraph("LISTAGEM DE ESTUDANTES E TEMAS APROVADOS", style_title))
    elements.append(Spacer(1, 0.8*cm))

    header = [
        Paragraph("Nº", style_header_table),
        Paragraph("Estudante", style_header_table),
        Paragraph("Título do Tema", style_header_table),
        Paragraph("Tutor/Orientador", style_header_table)
    ]
    
    dados_tabela = [header]
    
    temas = Tema.objects.filter(status_final='aprovado').select_related('estudante', 'tutor_indicado').order_by('estudante__nome')

    for i, tema in enumerate(temas, 1):
        nome_tutor = f"{tema.tutor_indicado.nome} {tema.tutor_indicado.sobrenome}" if tema.tutor_indicado else "A definir"
        
        linha = [
            Paragraph(str(i), style_cell),
            Paragraph(f"{tema.estudante.nome} {tema.estudante.sobrenome}", style_cell),
            Paragraph(tema.titulo, style_cell),
            Paragraph(nome_tutor, style_cell)
        ]
        dados_tabela.append(linha)

    tabela = Table(dados_tabela, colWidths=[1*cm, 5*cm, 8*cm, 4*cm])
    
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2c3e50')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.whitesmoke, colors.white])
    ]))
    
    elements.append(tabela)
    
    elements.append(Spacer(1, 1*cm))
    data_hoje = timezone.now().strftime('%d/%m/%Y às %H:%M')
    elements.append(Paragraph(f"Relatório extraído em: {data_hoje}", style_cell))

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data


@perfil_requerido(*PERFIS_GESTAO)
def exportar_todos_temas_pdf(request):
    pdf_conteudo = gerar_buffer_listagem_temas()
    
    response = HttpResponse(pdf_conteudo, content_type='application/pdf')
    data_str = timezone.now().strftime('%d_%m_%Y')
    nome_arq = f"Relatorio_Temas_Aprovados_{data_str}.pdf"
    
    response['Content-Disposition'] = f'attachment; filename="{nome_arq}"'
    
    return response


@perfil_requerido(*PERFIS_GESTAO)
def despachar_para_cientifica(request):
    if request.method == 'POST':
        temas_a_enviar = Tema.objects.filter(
            status_coordenacao='aprovado',
            listas_aprovadas__isnull=True
        )

        if temas_a_enviar.exists():
            nova_lista = ListaTemasAprovados.objects.create(
                codigo_referencia=f"REMESSA-{timezone.now().strftime('%Y%m%d-%H%M%S')}",
                enviado_por=request.user,
                status='enviado', 
                data_envio=timezone.now()
            )
            
            nova_lista.temas.set(temas_a_enviar)
            nova_lista.save()
            
            messages.success(request, f"Sucesso! {temas_a_enviar.count()} temas foram enviados para a Área Científica.")
        else:
            messages.warning(request, "Não existem novos temas aprovados pendentes de envio.")
  
        return redirect('lista_aprovados') 
    return redirect('lista_aprovados')


@perfil_requerido(*PERFIS_GESTAO)
def area_cientifica_temas(request):
    temas_aprovados = Tema.objects.filter(
        status_final='aprovado'
    ).select_related(
        'estudante__curso', 
        'tutor_indicado'
    ).order_by('estudante__curso__nome', 'data_envio')

    temas_por_curso = []
    
    for curso_nome, grupo in groupby(temas_aprovados, lambda x: x.estudante.curso.nome if x.estudante.curso else "Sem Curso"):
        temas_por_curso.append({
            'curso': curso_nome,
            'temas': list(grupo)
        })

    context = {
        'temas_por_curso': temas_por_curso,
    }

    return render(request, 'Area_Cientifica/temasaprovados.html', context)
