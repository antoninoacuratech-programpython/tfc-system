"""Solicitações de defesa e actas."""

import io
import os
import traceback
import zipfile

from django.conf import settings
from django.contrib import messages
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import ActaDefesa, Predefesa, SolicitacaoDefesa
from ..permissions import PERFIS_GESTAO, perfil_requerido


@perfil_requerido(*PERFIS_GESTAO)
def lista_solicitacoes_defesa(request):
    solicitacoes = SolicitacaoDefesa.objects.select_related(
        'predefesa__estudante', 
        'predefesa__tema__tutor_indicado',
        'chefe_departamento'
    ).filter(
        predefesa__estudante__curso=request.user.curso
    )
    
    return render(request, 'tfc/lista_solicitacoes.html', {'solicitacoes': solicitacoes})


@perfil_requerido(*PERFIS_GESTAO)
def detalhes_solicitacao_defesa(request, pk):
    solicitacao = get_object_or_404(SolicitacaoDefesa, pk=pk)
    return render(request, 'tfc/detalhes_solicitacao.html', {'solicitacao': solicitacao})


@perfil_requerido(*PERFIS_GESTAO)
def criar_solicitacao_defesa(request):
    predefesas_disponiveis = Predefesa.objects.filter(
        estudante__curso=request.user.curso,
        solicitacao_defesa__isnull=True
    ).select_related('estudante', 'tema')

    if request.method == "POST":
        predefesa_id = request.POST.get('predefesa_id')
        data = request.POST.get('data_defesa')
        hora = request.POST.get('hora_defesa')
        local = request.POST.get('local_defesa', 'Instalações do ISP-BIÉ')
        
        predefesa = get_object_or_404(Predefesa, id=predefesa_id)
        
        SolicitacaoDefesa.objects.create(
            predefesa=predefesa,
            data_defesa=data,
            hora_defesa=hora,
            local_defesa=local,
            chefe_departamento=request.user
        )
        
        messages.success(request, f"Solicitação para {predefesa.estudante.nome} registada com sucesso.")
        return redirect('lista_solicitacoes_defesa')
        
    return render(request, 'tfc/form_solicitacao.html', {
        'predefesas': predefesas_disponiveis
    })


def extrair_logica_pdf_solicitacao(buffer, solicitacao):
    pre = solicitacao.predefesa
    estudante = pre.estudante if pre else None
    tema = pre.tema if pre else None

    p = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    styles = getSampleStyleSheet()
    
    style_corpo = ParagraphStyle(
        'Corpo', parent=styles['Normal'], fontName='Helvetica',
        fontSize=11, leading=14, alignment=TA_JUSTIFY
    )

    relative_path = 'imgs/icons/finalispbie.jpg'
    logo_path = finders.find(relative_path)
    
    if not logo_path and hasattr(settings, 'STATIC_ROOT'):
        logo_path = os.path.join(settings.STATIC_ROOT, relative_path)
    
    if not logo_path and settings.STATICFILES_DIRS:
        logo_path = os.path.join(settings.STATICFILES_DIRS[0], relative_path)

    if logo_path and os.path.exists(logo_path):
        try:
            p.drawImage(logo_path, (width/2) - 40, height - 90, width=80, preserveAspectRatio=True, mask='auto')
        except Exception:
            pass 

    p.setFont("Helvetica-Bold", 12)
    p.drawCentredString(width/2, height - 120, "INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ")
    p.drawCentredString(width/2, height - 135, "DEPARTAMENTO DE ENGENHARIAS")
    
    p.setFont("Helvetica-Bold", 10)
    p.drawString(50, height - 170, "ASSUNTO: Pedido de autorização para a apresentação e defesa pública de TFC.")

    y = height - 210
    info_texto = [
        f"<b>Estudante:</b> {estudante.nome} {estudante.sobrenome}" if estudante else "<b>Estudante:</b> N/A",
        f"<b>Trabalho de Fim de Curso:</b> {tema.titulo if tema else 'Sem título'}",
        f"<b>Tutorado por:</b> {tema.tutor_indicado.nome if tema and tema.tutor_indicado else 'Não informado'}"
    ]

    for item in info_texto:
        para = Paragraph(item, style_corpo)
        w, h = para.wrap(width - 100, height)
        para.drawOn(p, 50, y - h)
        y -= (h + 12)

    corpo = ("Após o parecer emitido pelo júri nomeado para a avaliação deste trabalho de fim do curso (TFC), "
             "consideramos que o mesmo reúne as condições requeridas para a sua apresentação e defesa pública.")
    para_corpo = Paragraph(corpo, style_corpo)
    w, h = para_corpo.wrap(width - 100, height)
    para_corpo.drawOn(p, 50, y - 40)

    data_f = solicitacao.data_defesa.strftime('%d/%m/%Y') if solicitacao.data_defesa else "__/__/__"
    hora_f = solicitacao.hora_defesa.strftime('%H:%M') if solicitacao.hora_defesa else "__:__"
    agendamento = f"Assim, solicitamos que a mesma seja marcada para dia <b>{data_f}</b> pelas <b>{hora_f}</b> horas no <b>{solicitacao.local_defesa}</b>."
    para_age = Paragraph(agendamento, style_corpo)
    w, h = para_age.wrap(width - 100, height)
    para_age.drawOn(p, 50, y - 60 - h)

    p.drawCentredString(width/2, 200, "O Chefe do Departamento")
    p.drawCentredString(width/2, 185, "_______________________________________")
    if solicitacao.chefe_departamento:
        p.drawCentredString(width/2, 170, f"{solicitacao.chefe_departamento.nome} {solicitacao.chefe_departamento.sobrenome}")

    p.setFont("Helvetica", 8)
    p.drawCentredString(width/2, 45, "Rua Padre Fidalgo, Cidade do Cuito-Bié | NIF: 5000308765")
    
    p.showPage()
    p.save() 
    return buffer


@perfil_requerido(*PERFIS_GESTAO)
def gerar_pdf_solicitacao(request, pk):
    solicitacao = get_object_or_404(SolicitacaoDefesa, pk=pk)
    
    response = HttpResponse(content_type='application/pdf')
    nome_f = solicitacao.predefesa.estudante.nome.replace(" ", "_")
    response['Content-Disposition'] = f'attachment; filename="Solicitacao_{nome_f}.pdf"'
    
    extrair_logica_pdf_solicitacao(response, solicitacao)
    return response


@perfil_requerido(*PERFIS_GESTAO)
def baixar_todas_solicitacoes_zip(request):
    solicitacoes = SolicitacaoDefesa.objects.all()
    if not solicitacoes.exists():
        messages.warning(request, "Não há solicitações registradas.")
        return redirect('lista_solicitacoes_defesa')

    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, 'w') as zip_file:
        for s in solicitacoes:
            if s.predefesa and s.predefesa.estudante:
                pdf_buffer = io.BytesIO()
                extrair_logica_pdf_solicitacao(pdf_buffer, s)
                
                nome_f = f"Solicitacao_{s.predefesa.estudante.nome}_{s.id}.pdf".replace(" ", "_")
                zip_file.writestr(nome_f, pdf_buffer.getvalue())

    buffer_zip.seek(0)
    response = HttpResponse(buffer_zip.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="Todas_Solicitacoes_ISPB.zip"'
    return response


@perfil_requerido(*PERFIS_GESTAO)
def criar_acta(request):
    try:
        solicitacoes = SolicitacaoDefesa.objects.filter(
            acta_final__isnull=True, 
            predefesa__isnull=False
        ).select_related('predefesa__estudante', 'predefesa__tema')

        if request.method == "POST":
            sol_id = request.POST.get('solicitacao')
            
            ActaDefesa.objects.create(
                solicitacao_id=sol_id,
                numero_acta=request.POST.get('numero_acta'),
                data_sessao=request.POST.get('data_sessao'),
                local_sessao=request.POST.get('local_sessao', 'ISP-BI'),
                hora_abertura=request.POST.get('hora_abertura'),
                hora_encerramento=request.POST.get('hora_encerramento'),
                avaliacao_sessao=request.POST.get('avaliacao_sessao').replace(',', '.'),
                avaliacao_final=request.POST.get('avaliacao_final').replace(',', '.'),
                pontos_fortes=request.POST.get('pontos_fortes', ''),
                pontos_fracos=request.POST.get('pontos_fracos', ''),
                observacoes=request.POST.get('observacoes', '')
            )
            return redirect('lista_actas')

        return render(request, 'actas/form.html', {'solicitacoes': solicitacoes})

    except Exception as e:
        return HttpResponse(f"Erro Crítico de Dados: {e}. Verifique se todas as solicitações possuem pré-defesas.")


def gerar_conteudo_pdf_acta(acta):
    sol = acta.solicitacao
    pre = sol.predefesa if sol else None
    est = pre.estudante if pre else None
    tema = pre.tema if pre else None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5*cm, leftMargin=2.0*cm,
        topMargin=1.0*cm, bottomMargin=1.0*cm
    )
    
    elements = []
    style_n = ParagraphStyle(name='Normal', fontName='Helvetica', fontSize=10, leading=14)
    style_b = ParagraphStyle(name='Bold', parent=style_n, fontName='Helvetica-Bold')
    style_bc = ParagraphStyle(name='BoldCenter', parent=style_b, alignment=TA_CENTER, fontSize=11)
    style_j = ParagraphStyle(name='Justify', parent=style_n, alignment=TA_JUSTIFY)

    logo_path = finders.find('imgs/icons/finalispbie.jpg')
    if logo_path:
        try:
            img = Image(logo_path, width=2.5*cm, height=2.5*cm)
            elements.append(img)
        except: pass

    elements.append(Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_bc))
    elements.append(Paragraph("ACTA DA SESSÃO DE DEFESA DO TRABALHO DE FIM DE CURSO", style_bc))
    elements.append(Paragraph(f"ACTA N. {str(acta.numero_acta or '_______ /20___')}", style_bc))
    elements.append(Spacer(1, 0.5*cm))

    data_ext = acta.data_sessao.strftime('%d/%m/%Y') if acta.data_sessao else "_____/_____/____"
    local = str(acta.local_sessao or "_________________________")
    elements.append(Paragraph(f"Em {local}, aos {data_ext}", style_n))
    
    ano_val = getattr(sol, 'ano_letivo', getattr(sol, 'ano', '__________'))
    
    texto_estudante = (
        f"Esteve reunido o júri encarregue de avaliar o trabalho fim de curso de <b>{str(est.nome if est else '________________')}</b>. "
        f"Da especialidade de <b>{str(est.curso.nome if est and est.curso else '________________')}</b>. "
        f"Do Departamento de <b>{str(est.curso.departamento if est and est.curso else '________________')}</b> no ano lectivo de <b>{str(ano_val)}</b>."
    )
    elements.append(Paragraph(texto_estudante, style_j))
    elements.append(Spacer(1, 0.3*cm))

    elements.append(Paragraph(f"O Título do trabalho de Fim de Curso: <b>{str(tema.titulo if tema else '________________')}</b>", style_j))
    
    orientador = str(tema.tutor_indicado.nome if tema and tema.tutor_indicado else "________________")
    texto_orientacao = f"E foi orientado por <b>{orientador}</b> e Co-tutorado Por <b>________________</b> Docente (ou orientador convidado) do Departamento de <b>________________</b> ISP-BI."
    elements.append(Paragraph(texto_orientacao, style_j))
    
    dados_juri = [
        ["Presidente:", str(pre.presidente.nome if pre and pre.presidente else "________________"), "DEI", "________________"],
        ["1º Vogal:", str(pre.primeiro_vogal.nome if pre and pre.primeiro_vogal else "________________"), "DEI", "________________"],
        ["2º Vogal:", str(pre.segundo_vogal.nome if pre and pre.segundo_vogal else "________________"), "DEI", "________________"],
        ["Secretário:", str(pre.secretario.nome if pre and pre.secretario else "________________"), "DEI", "________________"]
    ]
    t_juri = Table(dados_juri, colWidths=[2.5*cm, 8.5*cm, 1.5*cm, 4.5*cm])
    t_juri.setStyle(TableStyle([('FONTNAME', (0,0), (0,-1), 'Helvetica-Bold'), ('LEFTPADDING', (0,0), (-1,-1), 0)]))
    elements.append(t_juri)
    elements.append(Spacer(1, 0.3*cm))

    texto_horario = f"O júri declarou a sessão Pública às <b>{str(acta.hora_abertura or '_______')}</b> e a sessão foi encerrada às <b>{str(acta.hora_encerramento or '_______')}</b>."
    elements.append(Paragraph(texto_horario, style_j))
    elements.append(Spacer(1, 0.4*cm))

    elements.append(Paragraph(f"<b>Pontos Fortes:</b> {str(acta.pontos_fortes or '________________')}", style_j))
    elements.append(Paragraph(f"<b>Pontos Fracos:</b> {str(acta.pontos_fracos or '________________')}", style_j))
    elements.append(Spacer(1, 0.4*cm))

    elements.append(Paragraph(f"Avaliação a sessão da defesa: <b>{str(acta.avaliacao_sessao or '_______')} Valores</b>", style_n))
    elements.append(Paragraph(f"Avaliação Final: <b>{str(acta.avaliacao_final or '_______')} Valores</b>", style_n))
    elements.append(Paragraph(f"Observações: {str(acta.observacoes or '________________')}", style_j))
    elements.append(Spacer(1, 1.0*cm))

    assinaturas = [
        [Paragraph("O Presidente<br/>_______________________", style_bc), Paragraph("1º Vogal<br/>_______________________", style_bc)],
        [Spacer(1, 1.2*cm), Spacer(1, 1.2*cm)],
        [Paragraph("2º Vogal<br/>_______________________", style_bc), Paragraph("O Secretário(a)<br/>_______________________", style_bc)]
    ]
    elements.append(Table(assinaturas, colWidths=[8.5*cm, 8.5*cm]))
    
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('Helvetica', 7)
        line1 = "Rua Padre Fidalgo, Cidade do Cuito-Bié"
        canvas.drawCentredString(A4[0]/2, 1.2*cm, line1)
        canvas.restoreState()

    doc.build(elements, onFirstPage=footer, onLaterPages=footer)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


@perfil_requerido(*PERFIS_GESTAO)
def baixar_acta_pdf(request, acta_id):
    try:
        acta = get_object_or_404(ActaDefesa, id=acta_id)
        pdf = gerar_conteudo_pdf_acta(acta)
        response = HttpResponse(pdf, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="Acta_{acta.numero_acta.replace("/", "-")}.pdf"'
        return response
    except Exception as e:
        return HttpResponse(f"Erro: {str(e)}", status=500)


@perfil_requerido(*PERFIS_GESTAO)
def baixar_todas_actas_zip(request):
    try:
        actas = ActaDefesa.objects.all()
        if not actas.exists():
            return HttpResponse("Não há actas para baixar.", status=404)

        buffer_zip = io.BytesIO()
        with zipfile.ZipFile(buffer_zip, 'w') as zip_file:
            for acta in actas:
                pdf_content = gerar_conteudo_pdf_acta(acta)
                
                nome_estudante = acta.solicitacao.predefesa.estudante.nome.replace(" ", "_")
                nome_pdf = f"Acta_{acta.numero_acta.replace('/', '-')}_{nome_estudante}.pdf"
                
                zip_file.writestr(nome_pdf, pdf_content)

        buffer_zip.seek(0)
        response = HttpResponse(buffer_zip.read(), content_type='application/zip')
        response['Content-Disposition'] = 'attachment; filename="Todas_Actas_ISP_BIE.zip"'
        return response
    except Exception as e:
        print(traceback.format_exc())
        return HttpResponse(f"Erro ao gerar ZIP: {str(e)}", status=500)


@perfil_requerido(*PERFIS_GESTAO)
def lista_actas(request):
    actas = ActaDefesa.objects.all().order_by('-criado_em')
    return render(request, 'actas/lista.html', {'actas': actas})


@perfil_requerido(*PERFIS_GESTAO)
def detalhe_acta(request, acta_id):
    acta = get_object_or_404(
        ActaDefesa.objects.select_related(
            'solicitacao__predefesa__estudante',
            'solicitacao__predefesa__tema',
            'solicitacao__predefesa__presidente',
            'solicitacao__predefesa__primeiro_vogal',
            'solicitacao__predefesa__segundo_vogal',
            'solicitacao__predefesa__secretario'
        ), 
        id=acta_id
    )
    
    return render(request, 'actas/detalhe.html', {'acta': acta})
