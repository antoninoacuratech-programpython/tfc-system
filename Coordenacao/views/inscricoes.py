"""Fichas de inscrição em TFC e respectiva aprovação."""

import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import Curso, InscricaoTFC, NotificacaoTFC, Tema
from ..permissions import PERFIS_GESTAO, perfil_requerido, garantir_acesso_estudante, mudar_para_perfil


@login_required
def lista_inscricoes_tfc(request):
    NotificacaoTFC.objects.filter(
        destinatario=request.user,
        destinatario_perfil='estudante',
        lida=False,
        inscricao__isnull=False
    ).update(lida=True)

    inscricoes = InscricaoTFC.objects.filter(estudante=request.user).order_by('-id')
    
    return render(request, 'tfc/lista_inscricoes.html', {'inscricoes': inscricoes})


@login_required
def gerar_ficha_tfc(request):
    tema_aprovado = Tema.objects.filter(estudante=request.user, status_final='aprovado').first()

    if not tema_aprovado:
        messages.error(request, "Acesso negado: Você precisa de um Tema Aprovado pela Coordenação.")
        return redirect('dashboard_estudante')

    if InscricaoTFC.objects.filter(estudante=request.user, tema=tema_aprovado).exists():
        messages.warning(request, "Você já possui uma inscrição submetida para este tema.")
        return redirect('lista_inscricoes_tfc')

    if request.method == "POST":
        try:
            inscricao = InscricaoTFC.objects.create(
                estudante=request.user,
                tema=tema_aprovado,
                periodo=request.POST.get('periodo'),
                endereco=request.POST.get('endereco'),
                local_desenvolvimento=request.POST.get('local_desenvolvimento'),
                requerimento=request.FILES.get('requerimento'),
                curriculum_academico=request.FILES.get('curriculum'),
                ficha_reconfirmacao=request.FILES.get('ficha_reconfirmacao'),
                comprovativo_pagamento=request.FILES.get('comprovativo_pagamento'),
                copia_bi=request.FILES.get('copia_bi'),
            )

            NotificacaoTFC.objects.create(
                remetente=request.user,
                destinatario_perfil='area_cientifica',
                mensagem=f"Nova inscrição de TFC submetida por: {request.user.nome}",
                inscricao=inscricao
            )

            messages.success(request, "Ficha de inscrição e documentos enviados com sucesso!")
            return redirect('lista_inscricoes_tfc')
        
        except Exception as e:
            messages.error(request, f"Erro ao processar inscrição: {e}")

    return render(request, 'tfc/form_inscricao.html', {'tema': tema_aprovado})


@login_required
def editar_inscricao_tfc(request, pk):
    inscricao = get_object_or_404(InscricaoTFC, pk=pk, estudante=request.user)
    
    if inscricao.status == 'aprovado':
        messages.error(request, "Esta inscrição já foi aprovada e não pode mais ser editada.")
        return redirect('lista_inscricoes_tfc')

    if request.method == "POST":
        inscricao.periodo = request.POST.get('periodo')
        inscricao.endereco = request.POST.get('endereco')
        inscricao.local_desenvolvimento = request.POST.get('local_desenvolvimento')

        if request.FILES.get('requerimento'):
            inscricao.requerimento = request.FILES.get('requerimento')
        
        if request.FILES.get('curriculum'):
            inscricao.curriculum_academico = request.FILES.get('curriculum')
            
        if request.FILES.get('ficha_reconfirmacao'):
            inscricao.ficha_reconfirmacao = request.FILES.get('ficha_reconfirmacao')
            
        if request.FILES.get('comprovativo_pagamento'):
            inscricao.comprovativo_pagamento = request.FILES.get('comprovativo_pagamento')

        if request.FILES.get('copia_bi'):
            inscricao.copia_bi = request.FILES.get('copia_bi')

        inscricao.save()
        messages.success(request, "Inscrição e documentos atualizados com sucesso!")
        return redirect('lista_inscricoes_tfc')

    return render(request, 'tfc/form_inscricao.html', {
        'inscricao': inscricao, 
        'tema': inscricao.tema, 
        'edit': True
    })


@login_required
def baixar_pdf_tfc(request, pk):
    inscricao = get_object_or_404(InscricaoTFC, pk=pk)
    estudante = inscricao.estudante
    garantir_acesso_estudante(request.user, estudante)
    tema = inscricao.tema
    
    depto_obj = estudante.depart or (estudante.curso.departamento if estudante.curso else None)
    nome_departamento = depto_obj.nome if depto_obj else ""

    orientador = tema.tutor_indicado if tema else None
    nome_orientador = f"{orientador.nome} {orientador.sobrenome}" if orientador else ""

    buffer = io.BytesIO()
    
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2.0*cm, leftMargin=3.0*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    elementos = []
    
    style_header = ParagraphStyle("Header", fontSize=10, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=12)
    style_label = ParagraphStyle("Label", fontSize=11, fontName="Helvetica", alignment=TA_LEFT, leading=18)
    style_title = ParagraphStyle("Title", fontSize=12, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=20)
    style_sig_label = ParagraphStyle("SigLabel", fontSize=11, fontName="Helvetica", alignment=TA_LEFT)
    style_sig_name = ParagraphStyle("SigName", fontSize=10, fontName="Helvetica-Bold", alignment=TA_CENTER)
    style_sig_sub = ParagraphStyle("SigSub", fontSize=9, fontName="Helvetica", alignment=TA_CENTER)

    def underline(text, width="________________________________"):
        content = str(text) if text and str(text).strip() else width
        return f"<u>{content}</u>"

    logo_path = finders.find('imgs/icons/finalispbie.jpg')
    header_content = [
        Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_header),
        Paragraph("DEPARTAMENTO DE INVESTIGAÇÃO CIENTÍFICA, INOVAÇÃO,", style_header),
        Paragraph("EMPREENDEDORISMO E PÓS-GRADUAÇÃO", style_header),
    ]
    try:
        logo_img = Image(logo_path, width=2.2*cm, height=2.2*cm)
    except:
        logo_img = Paragraph("<b>LOGO</b>", style_header)

    header_tab = Table([[logo_img, header_content]], colWidths=[2.5*cm, 13.5*cm])
    header_tab.setStyle(TableStyle([('VALIGN', (0,0), (-1,-1), 'MIDDLE')]))
    elementos.append(header_tab)
    elementos.append(Spacer(1, 15))

    num_ficha = str(inscricao.id).zfill(4)
    elementos.append(Paragraph(f"FICHA DE INSCRIÇÃO DO TRABALHO DE FIM DE CURSO Nº <u>{num_ficha}</u>.", style_title))

    elementos.append(Paragraph(f"Nome completo: {underline(f'{estudante.nome} {estudante.sobrenome}', '________________________________________________________')};", style_label))
    
    p_reg = "<b>[X] regular</b>" if str(inscricao.periodo).lower() == 'regular' else "[ ] regular"
    p_pos = "<b>[X] Pós-Laboral</b>" if str(inscricao.periodo).lower() == 'pós-laboral' else "[ ] Pós-Laboral"
    
    elementos.append(Paragraph(f"Curso: {underline(estudante.curso.nome if estudante.curso else '')}, Período: {p_reg} &nbsp;&nbsp;&nbsp; {p_pos} &nbsp;&nbsp;&nbsp; Departamento: {underline(nome_departamento)}, Nº universitário: {underline(estudante.id, '__________')};", style_label))
    elementos.append(Paragraph(f"Ano Académico: {underline(inscricao.data_criacao.year, '_______')}; Nacionalidade: {underline(inscricao.nacionalidade, '___________')}, Endereço: {underline(inscricao.endereco)} Telefone: {underline(estudante.telefone, '___________/___________')};", style_label))
    elementos.append(Paragraph(f"Email: {underline(estudante.email, '________________________________________')}, Ano de conclusão do Plano Curricular: {underline(inscricao.ano_conclusao_curriculo, '_______')};", style_label))

    elementos.append(Paragraph(f"Título do trabalho de fim de curso: {underline(tema.titulo if tema else '', '___________________________________________________________________________________')};", style_label))
    elementos.append(Paragraph(f"Local onde o trabalho será desenvolvido: {underline(inscricao.local_desenvolvimento, '_________________________________________')};", style_label))
    elementos.append(Paragraph(f"Orientador: {underline(nome_orientador, '_________________________')}; DEI {underline('', '________________________')};", style_label))
    elementos.append(Paragraph(f"Co-orientador: {underline('', '_________________________')}; DEI {underline('', '________________________')}.", style_label))

    elementos.append(Spacer(1, 15))
    dt = inscricao.data_criacao
    elementos.append(Paragraph(f"Cuito, aos <u>{dt.day:02d}</u>/<u>{dt.month:02d}</u>/<u>{dt.year}</u>.", style_label))
    elementos.append(Spacer(1, 2.5*cm))
    
    aprovador = inscricao.aprovado_por
    nome_conf = f"{aprovador.nome} {aprovador.sobrenome}" if aprovador else ""
    nome_est = f"{estudante.nome} {estudante.sobrenome}"

    assinaturas_data = [
        [Paragraph("Conferido por:", style_sig_label), Paragraph(underline(nome_conf, "________________________________________"), style_sig_name)],
        ["", Paragraph("", style_sig_sub)],
        [Spacer(1, 15), Spacer(1, 15)],
        [Paragraph("O estudante", style_sig_label), Paragraph(underline(nome_est, "________________________________________"), style_sig_name)],
        ["", Paragraph("", style_sig_sub)],
    ]

    tab_ass = Table(assinaturas_data, colWidths=[4.0*cm, 10.0*cm])
    tab_ass.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('BOTTOMPADDING', (0,0), (-1,-1), 8),
    ]))
    elementos.append(tab_ass)

    doc.build(elementos)
    buffer.seek(0)
    
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"Ficha_TFC_{estudante.id}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response


@perfil_requerido(*PERFIS_GESTAO)
def lista_inscricoes_pendentes(request):
    if request.user.perfil != "area_cientifica":
        messages.error(request, "Acesso restrito à Área Científica.")
        return redirect('admink')

    inscricoes = InscricaoTFC.objects.filter(status='pendente').order_by('-data_criacao')
    
    count = inscricoes.count()

    context = {
        'inscricoes': inscricoes,
        'inscricoes_pendentes_count': count,
        'titulo_pagina': "Inscrições Pendentes de Validação"
    }
    
    return render(request, 'Area_Cientifica/lista_pendentes.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def lista_cursos_fichas_pendentes(request):
    if request.user.perfil != "area_cientifica":
        messages.error(request, "Acesso restrito à Área Científica.")
        return redirect('admink')
    cursos_com_dados = (
        Curso.objects.all()
    )

    context = {
        'cursos_com_dados': cursos_com_dados,
        'titulo_pagina': "Validação por Curso"
    }
    
    return render(request, 'Area_Cientifica/fichas_por_curso_lista.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def fichas_pendentes_por_curso(request, curso_id):
    if request.user.perfil != "area_cientifica":
        messages.error(request, "Acesso restrito à Área Científica.")
        return redirect('admink')

    curso = get_object_or_404(Curso, id=curso_id)

    inscricoes = InscricaoTFC.objects.filter(
        status='pendente', 
        estudante__curso=curso  
    ).order_by('-data_criacao')
    
    count = inscricoes.count()

    context = {
        'curso': curso,
        'inscricoes': inscricoes,
        'inscricoes_pendentes_count': count,
        'titulo_pagina': f"Inscrições Pendentes - {curso.nome}"
    }
    
    return render(request, 'Area_Cientifica/fichas_por_curso_detalhe.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def historico_inscricoes(request):
    cursos = Curso.objects.all()
    temas_por_curso = []

    for curso in cursos:
        inscricoes = InscricaoTFC.objects.filter(
            estudante__curso=curso
        ).exclude(status='pendente').select_related('estudante', 'tema')

        if inscricoes.exists():
            temas_por_curso.append({
                'curso': curso.nome,
                'temas': inscricoes,
            })

    context = {
        'temas_por_curso': temas_por_curso,
    }
    return render(request, 'Area_Cientifica/historico_inscricoes.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def aprovar_inscricao_tfc(request, inscricao_id):
    ficha = get_object_or_404(InscricaoTFC, id=inscricao_id)
    ficha.status = 'aprovado'
    ficha.aprovado_por = request.user
    ficha.save()
    NotificacaoTFC.objects.filter(
        inscricao=ficha, 
        destinatario_perfil='area_cientifica', 
        lida=False
    ).update(lida=True)

    NotificacaoTFC.objects.create(
        remetente=request.user,
        destinatario=ficha.estudante,       
        destinatario_perfil='estudante',    
        mensagem=f"Sua ficha de inscrição para o tema '{ficha.tema.titulo}' foi aprovada com sucesso!",
        inscricao=ficha,
        lida=False
    )

    messages.success(request, f"Inscrição de {ficha.estudante.nome} aprovada com sucesso!")
    
    return redirect('lista_inscricoes_pendentes')


@perfil_requerido(*PERFIS_GESTAO)
def rejeitar_inscricao_tfc(request, inscricao_id):
    ficha = get_object_or_404(InscricaoTFC, id=inscricao_id)
    ficha.status = 'pendente' 
    ficha.save()
    NotificacaoTFC.objects.filter(
        inscricao=ficha, 
        destinatario_perfil='area_cientifica'
    ).update(lida=True)
    NotificacaoTFC.objects.create(
        remetente=request.user,
        destinatario=ficha.estudante,
        destinatario_perfil='estudante',
        mensagem=f"Sua inscrição para o tema '{ficha.tema.titulo}' não foi aprovada. Por favor, revise os dados ou contacte a Área Científica.",
        inscricao=ficha,
        lida=False
    )
    messages.error(request, f"Inscrição de {ficha.estudante.nome} foi rejeitada e o aluno notificado.")
    
    return redirect('lista_inscricoes_pendentes')


@perfil_requerido(*PERFIS_GESTAO)
def lista_inscricoes_aprovadas_coordenacao(request):
    if request.user.perfil != 'cordenacao' and not mudar_para_perfil(request, 'cordenacao'):
        messages.error(request, "Acesso restrito.")
        return redirect('admink')

    curso_coordenador = request.user.curso  
    if not curso_coordenador:
        messages.error(request, "Utilizador sem curso vinculado.")
        return redirect('admink')
    inscricoes_aprovadas = InscricaoTFC.objects.filter(
        status='aprovado',
        estudante__curso=curso_coordenador,
        enviado_para_coordenacao=True  
    ).order_by('-data_criacao')

    context = {
        'curso': curso_coordenador,
        'inscricoes': inscricoes_aprovadas,
        'total_aprovados': inscricoes_aprovadas.count(),
        'titulo_pagina': f"Inscrições Recebidas - {curso_coordenador.nome}"
    }
    return render(request, 'admin/inscricoes_aprovadas.html', context)


@perfil_requerido(*PERFIS_GESTAO)
def enviar_para_coordenacao(request, curso_id):
    if request.user.perfil != "area_cientifica":
        messages.error(request, "Acesso restrito.")
        return redirect('admink')

    curso = get_object_or_404(Curso, id=curso_id)

    fichas_para_enviar = InscricaoTFC.objects.filter(
        status='aprovado',
        estudante__curso=curso,
        enviado_para_coordenacao=False
    )

    if fichas_para_enviar.exists():
        quantidade = fichas_para_enviar.count()
        fichas_para_enviar.update(enviado_para_coordenacao=True)
        messages.success(request, f"Sucesso! {quantidade} inscrições foram enviadas para a coordenação de {curso.nome}.")
    else:
        messages.warning(request, "Não existem novas inscrições aprovadas prontas para envio neste curso.")

    return redirect('fichas_por_curso_detalhe', curso_id=curso.id)
