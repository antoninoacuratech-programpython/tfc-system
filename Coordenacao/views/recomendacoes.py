"""Recomendações dos tutores aos estudantes."""

import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    HRFlowable,
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..models import Recomendacao, Tema, Usuario
from ..permissions import garantir_acesso_estudante


@login_required
def adicionar_recomendacao(request, tema_id):
    if request.user.perfil != 'tutor':
        messages.error(request, "Acesso não autorizado.")
        return redirect('dashboard_tutor')

    tema = get_object_or_404(Tema, id=tema_id)

    recomendacoes = tema.recomendacoes.all().order_by('-data_criacao')

    if request.method == 'POST':
        texto = request.POST.get('texto', '').strip()
        if texto:
            Recomendacao.objects.create(
                tema=tema,
                tutor=request.user,
                texto=texto
            )
            messages.success(request, "Recomendação adicionada com sucesso.")
            return redirect('tutor_recomendacao', tema_id=tema.id)
        else:
            messages.error(request, "O campo de recomendação não pode estar vazio.")

    return render(request, 'tutor/recomendacao.html', {
        'tema': tema,
        'recomendacoes': recomendacoes
    })


@login_required
def todas_recomendacoes(request):
    temas_estudante = Tema.objects.filter(estudante=request.user)
    recomendacoes_qs = Recomendacao.objects.filter(tema__in=temas_estudante)
    total_novas = recomendacoes_qs.filter(lida=False).count()
    recomendacoes_qs.filter(lida=False).update(lida=True)

    context = {
        'recomendacoes': recomendacoes_qs.order_by('-data_criacao'),
    }
    return render(request, 'Estudante/todas_recomendacoes.html', context)


@login_required
def baixar_recomendacoes_pdf(request, estudante_id):
    estudante = get_object_or_404(Usuario, id=estudante_id)
    garantir_acesso_estudante(request.user, estudante)
    recomendacoes = Recomendacao.objects.filter(
        tema__estudante=estudante
    ).select_related('tutor', 'tema').order_by('-data_criacao')
    
    curso_obj = getattr(estudante, 'curso', None)
    nome_curso = curso_obj.nome.upper() if curso_obj else "NÃO INFORMADO"
    nome_depto = nome_curso.split()[0] if nome_curso else "GERAL"

    response = HttpResponse(content_type='application/pdf')
    nome_limpo = f"{estudante.nome}_{estudante.sobrenome}".replace(" ", "_")
    response['Content-Disposition'] = f'attachment; filename="Relatorio_{nome_limpo}.pdf"'

    doc = SimpleDocTemplate(
        response, 
        pagesize=A4, 
        rightMargin=50, leftMargin=50, topMargin=40, bottomMargin=60
    )
    elements = []

    styles = getSampleStyleSheet()
    
    style_inst_center = ParagraphStyle(
        'InstCenter', 
        fontSize=10, 
        fontName='Helvetica-Bold', 
        leading=14, 
        textColor=colors.HexColor("#1e293b"), 
        alignment=TA_CENTER
    )
    
    style_dept_center = ParagraphStyle(
        'DeptCenter', 
        fontSize=9, 
        fontName='Helvetica-Bold', 
        leading=12, 
        textColor=colors.HexColor("#64748b"), 
        alignment=TA_CENTER
    )

    style_h1 = ParagraphStyle('H1', fontSize=22, fontName='Helvetica-Bold', spaceAfter=10, textColor=colors.HexColor("#0f172a"), alignment=TA_LEFT)
    style_card_label = ParagraphStyle('CardLabel', fontSize=7, fontName='Helvetica-Bold', textColor=colors.HexColor("#94a3b8"), leading=10, spaceAfter=2)
    style_card_val = ParagraphStyle('CardVal', fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor("#1e293b"), leading=12)
    style_rec_header = ParagraphStyle('RecHeader', fontSize=10, fontName='Helvetica-Bold', textColor=colors.HexColor("#2563eb"))
    style_rec_date = ParagraphStyle('RecDate', fontSize=8, fontName='Helvetica', textColor=colors.HexColor("#94a3b8"), alignment=TA_RIGHT)
    style_body = ParagraphStyle('Body', fontSize=10, fontName='Helvetica', leading=14, textColor=colors.HexColor("#334155"), alignment=TA_JUSTIFY)

    relative_path = 'imgs/icons/finalispbie.jpg'
    logo_path = finders.find(relative_path) or os.path.join(settings.STATIC_ROOT, relative_path)
    
    try:
        logo = Image(logo_path, width=2.5*cm, height=2.5*cm)
    except:
        logo = Paragraph("<b>ISPB</b>", style_inst_center)

    header_text_content = [
        Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_inst_center),
        Paragraph(f"DEPARTAMENTO DE {nome_depto}", style_dept_center),
        Paragraph(f"CURSO DE {nome_curso}", style_dept_center),
    ]

    header_table = Table([[logo, header_text_content]], colWidths=[3*cm, 14*cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('LEFTPADDING', (1,0), (1,0), -1*cm),
    ]))
    
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    elements.append(Spacer(1, 20))

    elements.append(Paragraph("Relatório Académico", style_h1))
    elements.append(Spacer(1, 10))
    
    temas_qs = Tema.objects.filter(estudante=estudante)
    tema_titulo = temas_qs[0].titulo if temas_qs.exists() else "TEMA NÃO DEFINIDO"

    card_data = [
        [Paragraph("ESTUDANTE", style_card_label), Paragraph("TEMA DE INVESTIGAÇÃO", style_card_label)],
        [Paragraph(f"{estudante.nome} {estudante.sobrenome}".upper(), style_card_val), 
         Paragraph(tema_titulo.upper(), style_card_val)]
    ]
    
    card_table = Table(card_data, colWidths=[6*cm, 11*cm])
    card_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), colors.HexColor("#f8fafc")),
        ('BOX', (0,0), (-1,-1), 0.5, colors.HexColor("#e2e8f0")),
        ('ROUNDEDCORNERS', [8, 8, 8, 8]),
        ('PADDING', (0,0), (-1,-1), 12),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
    ]))
    elements.append(card_table)
    elements.append(Spacer(1, 35))

    elements.append(Paragraph("HISTÓRICO DE ORIENTAÇÕES", style_card_label))
    elements.append(Spacer(1, 12))

    if not recomendacoes.exists():
        elements.append(Paragraph("Nenhum registo de orientação encontrado.", style_body))
    else:
        for rec in recomendacoes:
            data_str = rec.data_criacao.strftime('%d %b %Y • %H:%M')
            tutor_nome = rec.tutor.nome.upper() if rec.tutor else "ORIENTADOR"
            
            rec_content = [
                [Paragraph(f"● {tutor_nome}", style_rec_header), Paragraph(data_str, style_rec_date)],
                [Paragraph(rec.texto, style_body), ""]
            ]
            
            rec_table = Table(rec_content, colWidths=[12*cm, 5*cm])
            rec_table.setStyle(TableStyle([
                ('SPAN', (0,1), (1,1)),
                ('TOPPADDING', (0,0), (-1,-1), 8),
                ('BOTTOMPADDING', (0,1), (-1,-1), 12),
                ('LINEBELOW', (0,1), (-1,1), 0.5, colors.HexColor("#f1f5f9")),
            ]))
            
            elements.append(KeepTogether(rec_table))
            elements.append(Spacer(1, 10))

    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 8)
        canvas.setFillColor(colors.HexColor("#94a3b8"))
        canvas.setStrokeColor(colors.HexColor("#f1f5f9"))
        canvas.line(50, 45, 545, 45)
        canvas.drawString(50, 30, "SGTF-ISPB | Sistema de Gestão de Trabalhos de Fim de Curso")
        canvas.drawRightString(545, 30, f"Documento Gerado Digitalmente • Pág. {doc.page}")
        canvas.restoreState()

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    return response
