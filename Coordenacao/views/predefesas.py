"""Agendamento, gestão e documentos de pré-defesas."""

import io
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models import Curso, ListaPreDefesas, Predefesa, Usuario
from ..permissions import PERFIS_GESTAO, perfil_requerido


@perfil_requerido(*PERFIS_GESTAO)
def agendar_predefesa(request):
    curso_coordenador = request.user.curso

    if request.method == 'POST':
        estudante_id = request.POST.get('estudante')
        data = request.POST.get('data')
        hora = request.POST.get('hora')
        secretario_id = request.POST.get('secretario')
        presidente_id = request.POST.get('presidente')
        v1_id = request.POST.get('v1')
        v2_id = request.POST.get('v2')

        try:
            nova_banca = Predefesa(
                data=data,
                hora=hora,
                estudante_id=estudante_id,
                secretario_id=secretario_id,
                presidente_id=presidente_id,
                primeiro_vogal_id=v1_id,
                segundo_vogal_id=v2_id
            )
            nova_banca.save()
            
            messages.success(request, "Pré-defesa agendada com sucesso!")
            return redirect('lista_predefesas')

        except ValidationError as e:
            if hasattr(e, 'message_dict'):
                for field, errors in e.message_dict.items():
                    for error in errors:
                        messages.error(request, f"{error}")
            else:
                for error in e.messages:
                    messages.error(request, f"{error}")
        except Exception as e:
            messages.error(request, f"Erro inesperado: {e}")

    estudantes_disponiveis = Usuario.objects.filter(
        perfil='estudante',
        curso=curso_coordenador
    ).exclude(
        minhas_predefesas__isnull=False
    )

    tutores_disponiveis = Usuario.objects.filter(
        perfil='tutor',
    )

    context = {
        'estudantes': estudantes_disponiveis,
        'tutores': tutores_disponiveis,
        'curso_atual': curso_coordenador 
    }
    
    return render(request, 'predefesa/form.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def lista_predefesas(request):
    curso_usuario = request.user.curso 
    predefesas = Predefesa.objects.select_related(
        'estudante', 'tema', 'presidente', 'primeiro_vogal', 'segundo_vogal'
    ).filter(
        estudante__curso=curso_usuario
    ).order_by('-data', '-hora')

    if request.user.is_superuser:
        predefesas = Predefesa.objects.select_related(
            'estudante', 'tema', 'presidente', 'primeiro_vogal', 'segundo_vogal'
        ).all().order_by('-data', '-hora')

    return render(request, 'predefesa/lista.html', {'predefesas': predefesas})


@perfil_requerido(*PERFIS_GESTAO)
def gerar_pdf_predefesa(request, pk):
    predefesa = get_object_or_404(Predefesa, pk=pk)
    estudante = predefesa.estudante
    
    curso_obj = getattr(estudante, 'curso', None)
    nome_curso = curso_obj.nome.upper() if curso_obj else "ENGENHARIA INFORMÁTICA"
    nome_depto = nome_curso.split()[0] if nome_curso else "ENGENHARIA"

    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=60
    )
    elements = []

    styles = getSampleStyleSheet()
    
    style_inst_center = ParagraphStyle(
        'InstCenter', fontSize=10, fontName='Helvetica-Bold', 
        leading=14, textColor=colors.HexColor("#1e293b"), alignment=TA_CENTER
    )
    
    style_dept_center = ParagraphStyle(
        'DeptCenter', fontSize=9, fontName='Helvetica-Bold', 
        leading=12, textColor=colors.HexColor("#64748b"), alignment=TA_CENTER
    )

    style_table_header = ParagraphStyle('TableHeader', fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=colors.whitesmoke)
    style_table_cell = ParagraphStyle('TableCell', fontSize=8, fontName='Helvetica', alignment=TA_CENTER)

    relative_path = 'imgs/icons/finalispbie.jpg'
    logo_path = finders.find(relative_path) or os.path.join(settings.STATIC_ROOT, relative_path)
    
    try:
        logo = Image(logo_path, width=2.2*cm, height=2.2*cm)
    except:
        logo = Paragraph("<b>ISPB</b>", style_inst_center)

    header_text_content = [
        Paragraph("REPÚBLICA DE ANGOLA", style_inst_center),
        Paragraph("MINISTÉRIO DO ENSINO SUPERIOR, CIÊNCIA, TECNOLOGIA E INOVAÇÃO", style_inst_center),
        Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_inst_center),
        Paragraph(f"DEPARTAMENTO DE {nome_depto}", style_dept_center),
        Paragraph(f"CURSO DE {nome_curso}", style_dept_center),
    ]

    header_table = Table([[logo, header_text_content]], colWidths=[2.5*cm, 14.5*cm])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elements.append(Spacer(1, 15))

    data_hoje = "14 de Janeiro de 2026"
    elements.append(Paragraph(data_hoje, ParagraphStyle('Date', alignment=TA_RIGHT, fontSize=10)))
    elements.append(Spacer(1, 15))
    
    elements.append(Paragraph("À: Direcção de Investigação Científica e Publicações.", styles['Normal']))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph("<b>Assunto:</b> Proposta do Júri para a Predefesa dos estudantes.", styles['Normal']))
    elements.append(Spacer(1, 20))

    juri_html = (
        f"<b>Presidente:</b> {predefesa.presidente.nome}{predefesa.presidente.sobrenome}<br/>"
        f"<b>1º Vogal:</b> {predefesa.primeiro_vogal.nome} {predefesa.primeiro_vogal.sobrenome}<br/>"
        f"<b>2º Vogal:</b> {predefesa.segundo_vogal.nome} {predefesa.segundo_vogal.sobrenome}<br/>"
        f"<b>Secretário:</b> {predefesa.secretario.nome}{predefesa.secretario.sobrenome}"
    )

    tabela_data = [
        [Paragraph("Nº", style_table_header), 
         Paragraph("Data", style_table_header), 
         Paragraph("Hora", style_table_header), 
         Paragraph("Estudante", style_table_header), 
         Paragraph("Tema", style_table_header), 
         Paragraph("Orientador", style_table_header), 
         Paragraph("Júri", style_table_header)],
        
        [Paragraph("1", style_table_cell),
         Paragraph(predefesa.data.strftime('%d/%m'), style_table_cell),
         Paragraph(predefesa.hora.strftime('%H:%M'), style_table_cell),
         Paragraph(f"{estudante.nome} {estudante.sobrenome}", style_table_cell),
         Paragraph(predefesa.tema.titulo if predefesa.tema else "---", style_table_cell),
         Paragraph(f"{predefesa.tema.tutor_indicado.nome}{predefesa.tema.tutor_indicado.sobrenome}"  if predefesa.tema and predefesa.tema.tutor_indicado else "---", style_table_cell),
         Paragraph(juri_html, ParagraphStyle('JuriStyle', fontSize=7, leading=9))]
    ]

    tabela = Table(tabela_data, colWidths=[0.8*cm, 1.2*cm, 1.2*cm, 3.5*cm, 4.5*cm, 3*cm, 4.8*cm])
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    
    elements.append(tabela)
    elements.append(Spacer(1, 50))

    elements.append(Paragraph("O Coordenador", style_inst_center))
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("_________________________", style_inst_center))
    elements.append(Paragraph("Daysel Labañino Griñan, MsC.", style_inst_center))

    doc.build(elements)
    
    buffer.seek(0)
    return HttpResponse(buffer, content_type='application/pdf')


@perfil_requerido(*PERFIS_GESTAO)
def gerar_pdf_todas_predefesas(request):
    predefesas = Predefesa.objects.select_related(
        'estudante', 'tema', 'presidente', 'primeiro_vogal', 'segundo_vogal', 'secretario'
    ).all().order_by('data', 'hora')

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, 
        pagesize=A4, 
        rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=60
    )
    elements = []

    styles = getSampleStyleSheet()
    style_inst_center = ParagraphStyle('InstCenter', fontSize=10, fontName='Helvetica-Bold', leading=14, alignment=TA_CENTER)
    style_dept_center = ParagraphStyle('DeptCenter', fontSize=9, fontName='Helvetica-Bold', leading=12, textColor=colors.HexColor("#64748b"), alignment=TA_CENTER)
    style_table_header = ParagraphStyle('TableHeader', fontSize=8, fontName='Helvetica-Bold', alignment=TA_CENTER, textColor=colors.whitesmoke)
    style_table_cell = ParagraphStyle('TableCell', fontSize=7, fontName='Helvetica', alignment=TA_CENTER)

    nome_depto = "ENGENHARIA" 
    nome_curso = "LISTA GERAL DE PRÉ-DEFESAS"

    relative_path = 'imgs/icons/finalispbie.jpg'
    logo_path = finders.find(relative_path) or os.path.join(settings.STATIC_ROOT, relative_path)
    try:
        logo = Image(logo_path, width=2.2*cm, height=2.2*cm)
    except:
        logo = Paragraph("<b>ISPB</b>", style_inst_center)

    header_text_content = [
        Paragraph("REPÚBLICA DE ANGOLA", style_inst_center),
        Paragraph("MINISTÉRIO DO ENSINO SUPERIOR, CIÊNCIA, TECNOLOGIA E INOVAÇÃO", style_inst_center),
        Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_inst_center),
        Paragraph(f"DEPARTAMENTO DE {nome_depto}", style_dept_center),
        Paragraph(f"{nome_curso}", style_dept_center),
    ]

    header_table = Table([[logo, header_text_content]], colWidths=[2.5*cm, 14.5*cm])
    header_table.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elements.append(Spacer(1, 15))

    data_hoje = "14 de Janeiro de 2026"
    elements.append(Paragraph(data_hoje, ParagraphStyle('Date', alignment=TA_RIGHT, fontSize=10)))
    elements.append(Spacer(1, 15))
    elements.append(Paragraph("À: Direcção de Investigação Científica e Publicações.", styles['Normal']))
    elements.append(Spacer(1, 5))
    elements.append(Paragraph("<b>Assunto:</b> Listagem Geral das Propostas de Júri para Pré-defesas.", styles['Normal']))
    elements.append(Spacer(1, 20))

    tabela_data = [
        [Paragraph("Nº", style_table_header), 
         Paragraph("Data", style_table_header), 
         Paragraph("Hora", style_table_header), 
         Paragraph("Estudante", style_table_header), 
         Paragraph("Tema", style_table_header), 
         Paragraph("Orientador", style_table_header), 
         Paragraph("Júri", style_table_header)]
    ]

    for i, p in enumerate(predefesas, 1):
        juri_html = (
            f"<b>Pres:</b> {p.presidente.nome}{p.presidente.sobrenome}<br/>"
            f"<b>1º Vog:</b> {p.primeiro_vogal.nome}{p.primeiro_vogal.sobrenome}<br/>"
            f"<b>2º Vog:</b> {p.segundo_vogal.nome}{p.segundo_vogal.sobrenome}<br/>"
            f"<b>Sec:</b> {p.secretario.nome}{p.secretario.sobrenome}"
        )
        
        linha = [
            Paragraph(str(i), style_table_cell),
            Paragraph(p.data.strftime('%d/%m'), style_table_cell),
            Paragraph(p.hora.strftime('%H:%M'), style_table_cell),
            Paragraph(f"{p.estudante.nome} {p.estudante.sobrenome}", style_table_cell),
            Paragraph(p.tema.titulo if p.tema else "---", style_table_cell),
            Paragraph(p.tema.tutor_indicado.nome if p.tema and p.tema.tutor_indicado else "---", style_table_cell),
            Paragraph(juri_html, ParagraphStyle('JuriStyle', fontSize=6, leading=8))
        ]
        tabela_data.append(linha)

    tabela = Table(tabela_data, colWidths=[0.7*cm, 1.1*cm, 1.1*cm, 3.2*cm, 4.8*cm, 3*cm, 5.1*cm], repeatRows=1)
    tabela.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,0), colors.HexColor("#1e293b")),
        ('GRID', (0,0), (-1,-1), 0.5, colors.black),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
    ]))
    
    elements.append(tabela)
    elements.append(Spacer(1, 40))

    elements.append(Paragraph("O Coordenador", style_inst_center))
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("_________________________", style_inst_center))
    elements.append(Paragraph("Daysel Labañino Griñan, MsC.", style_inst_center))

    doc.build(elements)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = 'attachment; filename="Lista_Geral_Predefesas.pdf"'
    return response


@perfil_requerido(*PERFIS_GESTAO)
def buscar_predefesas_por_curso(request):
    curso_id = request.GET.get('curso_id')
    
    predefesas = Predefesa.objects.filter(
        estudante__curso_id=curso_id,
        despacho_vinculado__isnull=True  
    ).select_related('estudante', 'tema')

    dados = [
        {
            'id': p.id,
            'estudante_nome': f"{p.estudante.nome} {p.estudante.sobrenome}",
            'tema_titulo': p.tema.titulo if p.tema else "Sem tema"
        } for p in predefesas
    ]
    return JsonResponse(dados, safe=False)


@perfil_requerido(*PERFIS_GESTAO)
def despachar_predefesas_cientifica(request):
    if request.method == 'POST':
        predefesas_a_enviar = Predefesa.objects.filter(
            listas__isnull=True
        )

        if predefesas_a_enviar.exists():
            nova_lista = ListaPreDefesas.objects.create(
                status='enviado'
            )
            
            nova_lista.predefesas.set(predefesas_a_enviar)
            nova_lista.save()
            
            messages.success(
                request, 
                f"Sucesso! {predefesas_a_enviar.count()} pré-defesas foram enviadas para a Área Científica."
            )
        else:
            messages.warning(request, "Não existem novas pré-defesas pendentes de envio.")
            
        return redirect('lista_predefesas') 
        
    return redirect('lista_predefesas')


@perfil_requerido(*PERFIS_GESTAO)
def lista_cursos_predefesas(request):
    todos_cursos = Curso.objects.all()
    
    cursos_com_dados = []
    
    for curso in todos_cursos:
        predefesas_enviadas = Predefesa.objects.filter(
            estudante__curso=curso,
            listas__status='enviado'
        ).distinct()
        
        if predefesas_enviadas.exists():
            cursos_com_dados.append({
                'curso': curso,
                'quantidade': predefesas_enviadas.count(),
                'ultimas_predefesas': predefesas_enviadas.order_by('-data')[:3]
            })

    context = {
        'cursos_com_dados': cursos_com_dados,
        'titulo_pagina': "Validação por Cursos"
    }
    return render(request, 'Area_Cientifica/lista_cursos.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def predefesas_por_curso(request, curso_id):
    curso = Curso.objects.get(id=curso_id)
    predefesas = Predefesa.objects.filter(
        estudante__curso=curso,
        listas__status='enviado'
    ).select_related('estudante', 'tema', 'presidente').order_by('data', 'hora')

    context = {
        'curso': curso,
        'predefesas': predefesas
    }
    return render(request, 'Area_Cientifica/detalhe_curso.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def editar_predefesa(request, pk):
    predefesa = get_object_or_404(Predefesa, pk=pk)
    tutores = Usuario.objects.filter(perfil='tutor')

    if request.method == 'POST':
        try:
            data = request.POST.get('data')
            hora = request.POST.get('hora')
            
            if data: predefesa.data = data
            if hora: predefesa.hora = hora

            predefesa.presidente_id = request.POST.get('presidente')
            predefesa.secretario_id = request.POST.get('secretario')
            predefesa.primeiro_vogal_id = request.POST.get('primeiro_vogal')
            predefesa.segundo_vogal_id = request.POST.get('segundo_vogal')

            predefesa.save()
            
            messages.success(request, "Agendamento atualizado com sucesso!")
            return redirect('lista_predefesas')

        except ValidationError as e:
            messages.error(request, f"Erro de Validação: {e.message if hasattr(e, 'message') else e}")
        except Exception as e:
            messages.error(request, f"Ocorreu um erro inesperado: {str(e)}")

    return render(request, 'predefesa/editar_predefesa.html', {
        'predefesa': predefesa,
        'tutores': tutores
    })


@perfil_requerido(*PERFIS_GESTAO)
def eliminar_predefesa(request, pk):
    predefesa = get_object_or_404(Predefesa, pk=pk)
    if request.method == 'POST' or request.method == 'GET': 
        nome_estudante = predefesa.estudante.nome
        predefesa.delete()
        messages.success(request, f"Agendamento de {nome_estudante} removido.")
    
    return redirect('lista_predefesas')
