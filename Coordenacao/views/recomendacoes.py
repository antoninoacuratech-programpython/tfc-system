"""Recomendações dos tutores aos estudantes."""

import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

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

from ..models import NotificacaoFinal, Recomendacao, Tema, Usuario
from ..permissions import PERFIL_ESTUDANTE, PERFIL_TUTOR, garantir_acesso_estudante, perfil_requerido


def _grupos(recomendacoes):
    """Separa as recomendações da banca (por pré-defesa) das do orientador."""
    banca, tutor = {}, []
    for r in recomendacoes:
        if r.predefesa_id:
            banca.setdefault(r.predefesa, []).append(r)
        else:
            tutor.append(r)
    sessoes = []
    for predefesa, recs in sorted(banca.items(), key=lambda kv: (kv[0].data, kv[0].hora), reverse=True):
        sessoes.append({
            "predefesa": predefesa,
            "fortes": [r for r in recs if r.tipo == "forte"],
            "melhorias": [r for r in recs if r.tipo == "melhoria"],
        })
    return sessoes, tutor


def _contagem(recomendacoes):
    acompanhaveis = [r for r in recomendacoes if r.acompanhavel]
    total = len(acompanhaveis)
    cumpridas = sum(1 for r in acompanhaveis if r.estado == "cumprida")
    return {
        "total": total,
        "cumpridas": cumpridas,
        "resolvidas": sum(1 for r in acompanhaveis if r.estado == "resolvida"),
        "pendentes": sum(1 for r in acompanhaveis if r.estado == "pendente"),
        "percentagem": round(cumpridas * 100 / total) if total else 0,
    }


def _visiveis(qs):
    # da banca só se mostram as de sessões já encerradas
    return qs.filter(Q(predefesa__isnull=True) | Q(predefesa__encerrada_em__isnull=False))


def _avisar(usuario, titulo, mensagem, link):
    if usuario:
        NotificacaoFinal.objects.create(usuario=usuario, titulo=titulo, mensagem=mensagem, link=link)


@perfil_requerido(PERFIL_TUTOR)
def adicionar_recomendacao(request, tema_id):
    tema = get_object_or_404(Tema.objects.select_related("estudante"), id=tema_id)
    if tema.tutor_indicado_id != request.user.pk:
        raise PermissionDenied("Só o orientador deste trabalho pode gerir as recomendações.")

    if request.method == "POST":
        texto = request.POST.get("texto", "").strip()
        if not texto:
            messages.error(request, "Escreva a recomendação antes de enviar.")
            return redirect("tutor_recomendacao", tema_id=tema.id)
        try:
            Recomendacao.objects.create(tema=tema, tutor=request.user, autor=request.user,
                                        funcao_autor="Orientador", texto=texto[:3000])
        except ValidationError as erro:
            messages.error(request, " ".join(erro.messages))
        else:
            messages.success(request, "Recomendação enviada ao estudante.")
        return redirect("tutor_recomendacao", tema_id=tema.id)

    recomendacoes = list(_visiveis(tema.recomendacoes.select_related("predefesa", "autor")).order_by("data_criacao"))
    sessoes, do_tutor = _grupos(recomendacoes)
    return render(request, "tutor/recomendacao.html", {
        "tema": tema,
        "sessoes": sessoes,
        "do_tutor": list(reversed(do_tutor)),
        "contagem": _contagem(recomendacoes),
    })


@perfil_requerido(PERFIL_ESTUDANTE)
def todas_recomendacoes(request):
    qs = _visiveis(Recomendacao.objects.filter(tema__estudante=request.user))
    qs.filter(lida=False).update(lida=True)
    recomendacoes = list(qs.select_related("predefesa", "autor", "tutor", "tema").order_by("data_criacao"))
    sessoes, do_tutor = _grupos(recomendacoes)
    return render(request, "Estudante/todas_recomendacoes.html", {
        "recomendacoes": recomendacoes,
        "sessoes": sessoes,
        "do_tutor": list(reversed(do_tutor)),
        "contagem": _contagem(recomendacoes),
        "tema": recomendacoes[0].tema if recomendacoes else Tema.objects.filter(estudante=request.user).last(),
    })


@login_required
@require_POST
def mudar_estado_recomendacao(request, rec_id):
    rec = get_object_or_404(Recomendacao.objects.select_related("tema__estudante", "tema__tutor_indicado"), pk=rec_id)
    tema, user, acao = rec.tema, request.user, request.POST.get("acao")
    agora = timezone.now()
    resumo = rec.texto[:90]
    pagina_tutor = reverse("tutor_recomendacao", args=[tema.pk]) + f"#rec-{rec.pk}"

    if not rec.acompanhavel:
        messages.error(request, "Os pontos fortes não precisam de acompanhamento.")
        return redirect("todas_recomendacoes" if user.pk == tema.estudante_id else "dashboard_tutor")

    if acao == "resolver" and user.pk == tema.estudante_id:
        if rec.estado == "cumprida":
            messages.info(request, "Esta recomendação já foi dada como cumprida.")
        else:
            nota = request.POST.get("nota", "").strip()[:2000]
            Recomendacao.objects.filter(pk=rec.pk).update(estado="resolvida", resolvida_em=agora, nota_estudante=nota)
            nome = f"{tema.estudante.nome} {tema.estudante.sobrenome}"
            _avisar(tema.tutor_indicado, "Recomendação resolvida", f"{nome} diz que resolveu: «{resumo}».", pagina_tutor)
            messages.success(request, "Marcada como resolvida. O orientador vai confirmar.")
        return redirect("todas_recomendacoes")

    if acao == "cumprir" and user.pk == tema.tutor_indicado_id:
        Recomendacao.objects.filter(pk=rec.pk).update(estado="cumprida", cumprida_em=agora, cumprida_por=user)
        _avisar(tema.estudante, "Recomendação cumprida", f"O orientador confirmou: «{resumo}».", reverse("todas_recomendacoes"))
        messages.success(request, "Recomendação dada como cumprida.")
        return redirect(pagina_tutor)

    if acao == "reabrir" and user.pk == tema.tutor_indicado_id:
        Recomendacao.objects.filter(pk=rec.pk).update(estado="pendente", cumprida_em=None, cumprida_por=None)
        _avisar(tema.estudante, "Recomendação por cumprir", f"O orientador considera que ainda falta: «{resumo}».",
                reverse("todas_recomendacoes"))
        messages.success(request, "Recomendação reaberta; o estudante foi avisado.")
        return redirect(pagina_tutor)

    raise PermissionDenied("Não pode alterar esta recomendação.")


@login_required
def baixar_recomendacoes_pdf(request, estudante_id):
    estudante = get_object_or_404(Usuario, id=estudante_id)
    garantir_acesso_estudante(request.user, estudante)
    recomendacoes = _visiveis(Recomendacao.objects.filter(
        tema__estudante=estudante
    )).select_related('tutor', 'autor', 'tema', 'predefesa').order_by('-data_criacao')
    
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
            quem = rec.autor or rec.tutor
            nome = f"{quem.nome} {quem.sobrenome}".upper() if quem else "ORIENTADOR"
            origem = f"Pré-defesa de {rec.predefesa.data:%d/%m/%Y}" if rec.predefesa_id else "Orientação"
            estado = "" if rec.tipo == "forte" else f" · {rec.get_estado_display()}"
            cabecalho = f"● {nome} ({rec.funcao_autor or 'Orientador'}) — {origem} · {rec.get_tipo_display()}{estado}"
            
            rec_content = [
                [Paragraph(cabecalho, style_rec_header), Paragraph(data_str, style_rec_date)],
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
