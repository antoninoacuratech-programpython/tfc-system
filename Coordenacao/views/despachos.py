"""Despachos: criação, envio à presidência, assinatura e PDFs."""

import io
import os
import zipfile

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from ..models import Curso, Despacho, Predefesa
from ..permissions import PERFIS_GESTAO, perfil_requerido, garantir_acesso_estudante


# --- FUNÇÃO MESTRE (Cria o conteúdo do Despacho) ---
def gerar_buffer_despacho(despacho):
    """
    Esta função contém toda a sua lógica funcional atual, 
    mas retorna um valor binário (bytes) em vez de uma HttpResponse.
    """
    predefesa = despacho.predefesa
    estudante = predefesa.estudante
    tema = predefesa.tema
    tutor = tema.tutor_indicado if tema else None
    titulo_tema = tema.titulo if tema else "(tema não definido)"

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        rightMargin=2.0*cm, leftMargin=2.5*cm,
        topMargin=1.5*cm, bottomMargin=1.5*cm
    )
    
    elements = []
    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle(name='Normal_ISP', parent=styles['Normal'], fontName='Helvetica', fontSize=10, leading=12)
    style_bold_center = ParagraphStyle(name='BoldCenter', parent=style_normal, fontName='Helvetica-Bold', alignment=TA_CENTER)
    style_justify = ParagraphStyle(name='Justify', parent=style_normal, alignment=TA_JUSTIFY, leading=14)
    style_center = ParagraphStyle(name='Center', parent=style_normal, alignment=TA_CENTER)

    # --- Inserção do Logotipo ---
    relative_path = 'imgs/icons/finalispbie.jpg'
    logo_path = finders.find(relative_path) or os.path.join(settings.STATIC_ROOT, relative_path)
    
    try:
        logo = Image(logo_path, width=2.2*cm, height=2.2*cm)
        elements.append(logo)
    except:
        elements.append(Paragraph("<b>INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ</b>", style_bold_center))

    elements.append(Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_bold_center))
    elements.append(Paragraph("GABINETE DO PRESIDENTE", style_bold_center))
    elements.append(Spacer(1, 0.6*cm))
    
    elements.append(Paragraph(f"DESPACHO Nº {despacho.numero_despacho}", style_bold_center))
    elements.append(Spacer(1, 0.6*cm))

    elements.append(Paragraph(f"<b>Considerando</b> que nos termos do {despacho.referencia_legal_1}, o estudante conclui o plano curricular do curso com aprovação em todas unidades curriculares do ciclo de formação e a realização da Pré-defesa Pública do Trabalho de Fim de Curso;", style_justify))
    elements.append(Spacer(1, 0.3*cm))
    
    elements.append(Paragraph(f"<b>Considerando ainda</b> que, a estudante <b>{estudante.nome} {estudante.sobrenome}</b>, terminou com aproveitamento positivo a parte curricular do curso de {estudante.curso.nome}, período Regular.", style_justify))
    elements.append(Spacer(1, 0.3*cm))
    

    elements.append(Paragraph(f"<b>Havendo a necessidade</b> de se nomear o júri para avaliar o Trabalho de Fim de Curso com o título: <b>{titulo_tema}.</b> Local de desenvolvimento: <b>{despacho.local_desenvolvimento}</b>", style_justify))
    elements.append(Spacer(1, 0.3*cm))
    
    nome_tutor = f"{tutor.nome} {tutor.sobrenome}" if tutor else "A definir"
    elements.append(Paragraph(f"<b>Orientado (a)</b> pelo (a) Docente: <b>{nome_tutor}.</b>", style_justify))
    elements.append(Spacer(1, 0.3*cm))
    
    elements.append(Paragraph(f"O Presidente do Instituto Superior Politécnico do Bié (ISP-Bi), usando das competências que lhe são conferidas pela {despacho.referencia_legal_2};", style_justify))
    elements.append(Spacer(1, 0.5*cm))

    elements.append(Paragraph("<b>DETERMINA</b>", style_bold_center))
    elements.append(Spacer(1, 0.4*cm))
    elements.append(Paragraph("Nomear o júri da Pré-Defesa Pública de Trabalho de Fim de Curso;", style_justify))
    elements.append(Spacer(1, 0.3*cm))

    dados_juri = [
        [Paragraph("O júri acima referido tem a seguinte composição:", style_justify), ""],
        [Paragraph("<b>Presidente</b>", style_normal), f"{predefesa.presidente.nome} {predefesa.presidente.sobrenome}"],
        [Paragraph("<b>1º Vogal</b>", style_normal), f"{predefesa.primeiro_vogal.nome} {predefesa.primeiro_vogal.sobrenome}"],
        [Paragraph("<b>2º Vogal</b>", style_normal), f"{predefesa.segundo_vogal.nome} {predefesa.segundo_vogal.sobrenome}"],
        [Paragraph("<b>Secretário (a)</b>", style_normal), f"{predefesa.secretario.nome} {predefesa.secretario.sobrenome}" if predefesa.secretario else "---"]
    ]
    
    tabela_juri = Table(dados_juri, colWidths=[4*cm, 11*cm])
    tabela_juri.setStyle(TableStyle([
        ('SPAN', (0, 0), (1, 0)),
        ('LEFTPADDING', (0, 0), (-1, -1), 0),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(tabela_juri)
    elements.append(Spacer(1, 0.5*cm))

    data_formatada = predefesa.data.strftime('%d de %B de %Y')
    elements.append(Paragraph(f"A sessão da Pré-Defesa será realizada no dia {data_formatada}, na Coordenação de {estudante.curso.nome}, pelas {predefesa.hora} horas.", style_justify))
    elements.append(Spacer(1, 0.3*cm))
    elements.append(Paragraph("O presente Despacho entra imediatamente em vigor a partir da data da sua publicação.", style_justify))
    elements.append(Spacer(1, 0.6*cm))
    
    elements.append(Paragraph("<b>PUBLIQUE-SE</b>", style_center))
    elements.append(Spacer(1, 0.4*cm))
    
    data_emissao = despacho.data_emissao.strftime('%d DE %B DE %Y').upper()
    elements.append(Paragraph(f"GABINETE DO PRESIDENTE DO INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ, {despacho.local_emissao.upper()}, AOS {data_emissao}.", style_center))
    

    # Assinatura
    nome_presidente = f"{despacho.aprovado_por.nome} {despacho.aprovado_por.sobrenome}" if despacho.aprovado_por else "A ASSINAR"
    elements.append(Spacer(1, 1.5*cm))
    elements.append(Paragraph("<b>O PRESIDENTE</b>", style_center))
    elements.append(Spacer(1, 1.2*cm))
    elements.append(Paragraph("_____________________________ ", style_center))
    elements.append(Paragraph(f"<b>{nome_presidente}</b>", style_center))

    doc.build(elements)
    pdf_data = buffer.getvalue()
    buffer.close()
    return pdf_data


# --- VIEW 1: DOWNLOAD INDIVIDUAL ---
@login_required
def gerar_despacho_pdf(request, despacho_id):
    despacho = get_object_or_404(Despacho, id=despacho_id)
    garantir_acesso_estudante(request.user, despacho.predefesa.estudante)
    pdf_conteudo = gerar_buffer_despacho(despacho)
    
    response = HttpResponse(pdf_conteudo, content_type='application/pdf')
    nome_arq = f"Despacho_{despacho.predefesa.estudante.nome}_{despacho.ano_letivo}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{nome_arq}"'
    return response


# --- VIEW 2: DOWNLOAD ZIP ---
@perfil_requerido(*PERFIS_GESTAO)
def baixar_todos_despachos_zip(request):
    despachos = Despacho.objects.all()
    if not despachos.exists():
        messages.warning(request, "Não há despachos para baixar.")
        return redirect('lista_despachos')

    buffer_zip = io.BytesIO()
    with zipfile.ZipFile(buffer_zip, 'w') as zip_file:
        for d in despachos:
            try:
                # Gera o binário do PDF para este despacho
                pdf_data = gerar_buffer_despacho(d)
                
                # Nome do arquivo dentro do ZIP
                estudante_nome = d.predefesa.estudante.nome.replace(" ", "_")
                filename = f"Despacho_{d.numero_despacho}_{estudante_nome}.pdf"
                
                zip_file.writestr(filename, pdf_data)
            except Exception as e:
                # Se um PDF falhar (ex: falta de dados), continua para o próximo
                continue

    buffer_zip.seek(0)
    response = HttpResponse(buffer_zip.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="Despachos_Presidente_ISPB.zip"'
    return response


@perfil_requerido(*PERFIS_GESTAO)
def criar_despacho(request):
    if request.method == 'POST':
        predefesa_id = request.POST.get('predefesa')
        numero = request.POST.get('numero_despacho')
        local = request.POST.get('local_desenvolvimento')

        # validacao de predefesa se existe ///
        if not predefesa_id:
            messages.error(request, "Erro: Você deve selecionar um estudante/pré-defesa.")
            return redirect('criar_despacho')

        if Despacho.objects.filter(numero_despacho=numero).exists():
            messages.warning(request, f"O despacho nº {numero} já existe no sistema. Por favor, use uma numeração diferente.")
            return render(request, 'tfc/criar_despacho.html', {
                'cursos': Curso.objects.all(),
                'numero_repetido': numero 
            })

        try:
            predefesa = Predefesa.objects.get(id=int(predefesa_id))
            user = request.user if request.user.is_authenticated else None

            Despacho.objects.create(
                predefesa=predefesa,
                numero_despacho=numero,
                local_desenvolvimento=local,
                criado_por=user
            )
            messages.success(request, "Despacho criado com sucesso!")
            return redirect('listar_despachos')
            
        except (Predefesa.DoesNotExist, ValueError, TypeError):
            messages.error(request, "A pré-defesa selecionada é inválida ou não existe.")
        except Exception as e:
            messages.error(request, f"Erro inesperado no servidor: {e}")

    cursos = Curso.objects.all()
    return render(request, 'tfc/criar_despacho.html', {'cursos': cursos})


# --- 1. VIEW PARA ENVIAR À PRESIDÊNCIA (Área Científica) ---
@perfil_requerido(*PERFIS_GESTAO)
def enviar_despacho_presidencia(request, despacho_id):
    if request.method == 'POST':
        despacho = get_object_or_404(Despacho, id=despacho_id)
        
        
        if despacho.status != 'pendente' and despacho.status != 'rascunho':
            messages.error(request, f"O despacho nº {despacho.numero_despacho} já foi processado ou enviado anteriormente.")
            return redirect('listar_despachos')
            

        despacho.status = 'enviado'
        despacho.save()
        
        messages.success(request, f"Despacho nº {despacho.numero_despacho} enviado com sucesso para a Presidência!")
        return redirect('listar_despachos')
        
    return redirect('listar_despachos')


# --- 2. VIEW PARA ASSINAR OU REJEITAR O DESPACHO (Presidente) ---
@perfil_requerido(*PERFIS_GESTAO)
def assinar_despacho(request, despacho_id):
    """
    O Presidente visualiza o despacho e decide se vai Assinar (Aprovar) 
    ou Rejeitar o documento.
    """
    despacho = get_object_or_404(Despacho, id=despacho_id)

    # Segurança básica de perfil (ajuste se o campo no seu modelo for diferente)
    if not request.user.is_authenticated or request.user.perfil != 'presidente':
        messages.error(request, "Acesso negado. Apenas o Presidente pode assinar despachos.")
        return redirect('listar_despachos')

    if request.method == 'POST':
        acao = request.POST.get('acao') # Captura qual botão o presidente clicou

        if acao == 'aprovar':
            despacho.status = 'aprovado'
            despacho.aprovado_por = request.user  # Guarda quem assinou
            despacho.publicado = True             # Entra em vigor
            despacho.save()
            messages.success(request, f"Despacho nº {despacho.numero_despacho} assinado e aprovado com sucesso!")
            
        elif acao == 'rejeitar':
            despacho.status = 'rejeitado'
            despacho.save()
            messages.warning(request, f"Despacho nº {despacho.numero_despacho} foi rejeitado.")
        
        else:
            messages.error(request, "Ação inválida.")

        return redirect('listar_despachos')

    # Se for GET, renderiza a página com os detalhes para o presidente ler antes de assinar
    return render(request, 'tfc/revisar_despacho.html', {'despacho': despacho})


@perfil_requerido(*PERFIS_GESTAO)
def listar_despachos(request):
    despachos = Despacho.objects.all().select_related(
        'predefesa__estudante', 
        'predefesa__estudante__curso',
        'aprovado_por'
    ).order_by('-criado_em')
    
    return render(request, 'tfc/listar_despachos.html', {'despachos': despachos})


@perfil_requerido(*PERFIS_GESTAO)
def eliminar_despacho(request, pk):
    despacho = get_object_or_404(Despacho, pk=pk)
    
    if request.method == 'POST':
        numero = despacho.numero_despacho
        despacho.delete()
        messages.success(request, f"O despacho Nº {numero} foi removido com sucesso.")
        return redirect('listar_despachos')
    return redirect('listar_despachos')
