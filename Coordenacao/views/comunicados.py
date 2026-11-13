"""Comunicados oficiais e respectivos PDFs."""

import io
import os

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
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

from ..models import Comunicado, Notificacao, Usuario
from ..permissions import PERFIS_GESTAO, perfil_requerido


@perfil_requerido(*PERFIS_GESTAO)
def criar_comunicado(request):
    if request.method == "POST":
        Comunicado.objects.create(
            data_inicio=request.POST["data_inicio"],
            data_fim=request.POST["data_fim"],
            hora_inicio=request.POST["hora_inicio"],
            hora_fim=request.POST["hora_fim"],
            taxa_finalistas_antigos=request.POST.get("taxa_finalistas_antigos", 10000),
            taxa_pos_laboral_tfc=request.POST.get("taxa_pos_laboral_tfc", 75000),
            taxa_pos_laboral_exame=request.POST.get("taxa_pos_laboral_exame", 30000),
        )
        messages.success(request, "Comunicado criado com sucesso.")
        return redirect("lista_comunicados")

    return render(request, "comunicados/criar.html")


@perfil_requerido(*PERFIS_GESTAO)
def lista_comunicados(request):
    from django.db.models import Q
    
    # Pega o termo de pesquisa do input name="q"
    query = request.GET.get('q', '')
    
    if query:
        # Pesquisa por data_inicio ou data_fim que contenha o texto digitado
        comunicados = Comunicado.objects.filter(
            Q(data_inicio__icontains=query) | 
            Q(data_fim__icontains=query)
        ).order_by("-id")
    else:
        # Se não houver pesquisa, mostra todos como você já fazia
        comunicados = Comunicado.objects.all().order_by("-id")
    
    return render(
        request,
        "comunicados/lista.html",
        {
            "comunicados": comunicados,
            "query": query,
            "total_comunicados": comunicados.count()
        }
    )


@perfil_requerido(*PERFIS_GESTAO)
def atualizar_comunicado(request, pk):
    from django.shortcuts import get_object_or_404
    comunicado = get_object_or_404(Comunicado, pk=pk)

    if request.method == "POST":
        comunicado.data_inicio = request.POST["data_inicio"]
        comunicado.data_fim = request.POST["data_fim"]
        comunicado.hora_inicio = request.POST["hora_inicio"]
        comunicado.hora_fim = request.POST["hora_fim"]
        comunicado.taxa_finalistas_antigos = request.POST.get("taxa_finalistas_antigos", 10000)
        comunicado.taxa_pos_laboral_tfc = request.POST.get("taxa_pos_laboral_tfc", 75000)
        comunicado.taxa_pos_laboral_exame = request.POST.get("taxa_pos_laboral_exame", 30000)
        comunicado.save()
        
        messages.success(request, "Comunicado atualizado com sucesso.")
        return redirect("lista_comunicados")

    return render(request, "comunicados/atualizar.html", {"comunicado": comunicado})


@perfil_requerido(*PERFIS_GESTAO)
def eliminar_comunicado(request, pk):
    from django.shortcuts import get_object_or_404
    comunicado = get_object_or_404(Comunicado, pk=pk)
    
    if request.method == "POST":
        comunicado.delete()
        messages.success(request, "Comunicado eliminado com sucesso.")
        return redirect("lista_comunicados")
    
    # A eliminação só é feita via POST (confirmada na lista de comunicados).
    return redirect("lista_comunicados")


@perfil_requerido(*PERFIS_GESTAO)
def publicar_comunicado(request, id):
    comunicado = get_object_or_404(Comunicado, id=id)

    if not comunicado.publicado:
        comunicado.publicado = True
        comunicado.data_publicacao = timezone.now()
        comunicado.save()

        usuarios = Usuario.objects.all()
        Notificacao.objects.bulk_create([
            Notificacao(usuario=u, comunicado=comunicado)
            for u in usuarios
        ])

        messages.success(
            request,
            "Comunicado publicado e notificações enviadas."
        )

    return redirect("lista_comunicados")


def texto_comunicado_oficial(comunicado):
    data_inicio = comunicado.data_inicio.strftime("%d/%m/%Y")
    data_fim = comunicado.data_fim.strftime("%d/%m/%Y")
    hora_inicio = comunicado.hora_inicio.strftime("%H:%M")
    hora_fim = comunicado.hora_fim.strftime("%H:%M")

    return f"""
Torna-se público que, no período compreendido entre {data_inicio} e {data_fim},
no horário das {hora_inicio} às {hora_fim}, estarão a decorrer atividades académicas
relacionadas com os Trabalhos de Fim de Curso (TFC).

Todos os estudantes e docentes envolvidos deverão comparecer pontualmente,
respeitando as normas institucionais em vigor.

O presente comunicado entra em vigor na data da sua publicação.
"""


def gerar_comunicado_pdf(comunicado, caminho_pdf,
                         nome_depto, nome_curso):

    styles = getSampleStyleSheet()

    style_inst_center = ParagraphStyle(
        "inst",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        leading=13,
        fontName="Helvetica-Bold"
    )

    style_dept_center = ParagraphStyle(
        "dept",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=9,
        leading=12,
        fontName="Helvetica-Bold"
    )

    style_normal = ParagraphStyle(
        "normal",
        parent=styles["Normal"],
        fontSize=11,
        leading=16,
        spaceBefore=8,
        spaceAfter=8
    )

    doc = SimpleDocTemplate(
        caminho_pdf,
        pagesize=A4,
        rightMargin=2.5 * cm,
        leftMargin=2.5 * cm,
        topMargin=2.5 * cm,
        bottomMargin=2.5 * cm
    )

    elementos = []

    # --- CABEÇALHO INSTITUCIONAL (Logo + Texto) ---
    relative_path = "imgs/icons/finalispbie.jpg"
    logo_path = (
        finders.find(relative_path)
        or os.path.join(settings.STATIC_ROOT or "", relative_path)
    )

    try:
        logo = Image(logo_path, width=2.2 * cm, height=2.2 * cm)
    except Exception:
        logo = Paragraph("<b>ISPB</b>", style_inst_center)

    header_text = [
        Paragraph("REPÚBLICA DE ANGOLA", style_inst_center),
        Paragraph(
            "MINISTÉRIO DO ENSINO SUPERIOR, CIÊNCIA, TECNOLOGIA E INOVAÇÃO",
            style_inst_center
        ),
        Paragraph(
            "INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ",
            style_inst_center
        ),
        Paragraph(
            f"DEPARTAMENTO DE {nome_depto.upper()}",
            style_dept_center
        ),
        Paragraph(
            f"CURSO DE {nome_curso.upper()}",
            style_dept_center
        ),
    ]

    header = Table(
        [[logo, header_text]],
        colWidths=[3 * cm, 13 * cm]
    )

    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))

    elementos.append(header)
    elementos.append(Spacer(1, 15))
    elementos.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    elementos.append(Spacer(1, 20))

    # --- TÍTULO ---
    elementos.append(Paragraph(
        "COMUNICADO",
        ParagraphStyle(
            "title",
            alignment=TA_CENTER,
            fontSize=14,
            fontName="Helvetica-Bold",
            spaceAfter=20
        )
    ))

    # --- CORPO ---
    from .utils import texto_comunicado_oficial  # ajusta se estiver noutro ficheiro

    corpo = texto_comunicado_oficial(comunicado)
    for linha in corpo.split("\n"):
        if linha.strip():
            elementos.append(Paragraph(linha, style_normal))

    # --- ASSINATURAS ---
    elementos.append(Spacer(1, 30))

    elementos.append(Paragraph(
        "Homologação<br/><br/>______/_____/_______<br/><br/>"
        "Professor Doutor Fernando Maia<br/>"
        "«Professor Catedrático»",
        styles["Normal"]
    ))

    elementos.append(Spacer(1, 30))

    elementos.append(Paragraph(
        "A Chefe do Departamento de Investigação Científica<br/><br/>"
        "_____________________________<br/>"
        "Ana Angelina Cangombe",
        styles["Normal"]
    ))

    # --- RODAPÉ ---
    elementos.append(Spacer(1, 40))
    elementos.append(Paragraph(
        "Rua Padre Fidalgo entre Artur de Paiva e Francisco de Leite Cardoso S/N, "
        "Cidade do Cuito-Bié<br/>"
        "E-mail: ispb.bie@gmail.com | NIF: 5000308765<br/>"
        "Telefone: 922408061 | http://isp-bie.ao/",
        ParagraphStyle(
            "footer",
            fontSize=8,
            alignment=TA_CENTER,
            textColor=colors.grey
        )
    ))

    doc.build(elementos)


@login_required
def baixar_comunicado_pdf(request, id):
    comunicado = get_object_or_404(Comunicado, id=id)
    buffer = io.BytesIO()

    # --- Configuração do Documento ---
    # Margem esquerda de 3cm para seguir o padrão oficial
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2.0*cm, leftMargin=3.0*cm,
                            topMargin=1.5*cm, bottomMargin=1.5*cm)
    elementos = []
    
    # --- Estilos Personalizados ---
    style_header = ParagraphStyle("Header", fontSize=10, fontName="Helvetica-Bold", alignment=TA_CENTER, leading=12)
    style_title = ParagraphStyle("Title", fontSize=14, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=10, spaceBefore=10)
    style_body = ParagraphStyle("Body", fontSize=10.5, fontName="Helvetica", alignment=TA_JUSTIFY, leading=13, spaceAfter=8)
    style_footer_text = ParagraphStyle("Footer", fontSize=7.5, fontName="Helvetica", alignment=TA_CENTER, textColor=colors.black)
    style_homolog = ParagraphStyle("Homolog", fontSize=8.5, fontName="Helvetica", alignment=TA_LEFT, leading=10)

    # --- 1. Estrutura de Cabeçalho Superior ---
    relative_path = 'imgs/icons/finalispbie.jpg'
    logo_path = finders.find(relative_path)
    
    logo_w = 2.8*cm  # Largura fixa do logo e da homologação
    try:
        logo_img = Image(logo_path, width=logo_w, height=2.8*cm)
    except:
        logo_img = Paragraph("<b>LOGO</b>", style_header)

    # Conteúdo da Coluna da Esquerda (Logo + Homologação)
    col_esquerda = [
        logo_img,
        Spacer(1, 10),
        Paragraph("<b>Homologação</b>", style_homolog),
        Paragraph("______/_____/_______", style_homolog),
        Spacer(1, 10),
        Paragraph("<b>Professor Doutor.</b>", style_homolog),
        Paragraph("<b>Fernando Maia</b>", style_homolog),
        Paragraph("<i>Professor Catedrático</i>", style_homolog),
    ]

    # Conteúdo da Coluna da Direita (Nomes da Instituição)
    col_direita = [
        Spacer(1, 0.5*cm), # Alinhamento vertical com o topo do logo
        Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_header),
        Paragraph("DEPARTAMENTO DE INVESTIGAÇÃO CIENTÍFICA, INOVAÇÃO,", style_header),
        Paragraph("EMPREENDEDORISMO E PÓS-GRADUAÇÃO", style_header),
    ]

    # Tabela Mestra do Cabeçalho
    # Coluna 1: 3cm (Logo/Homolog) | Coluna 2: 12.5cm (Texto Institucional)
    header_master = Table([[col_esquerda, col_direita]], colWidths=[logo_w + 0.5*cm, 12.0*cm])
    header_master.setStyle(TableStyle([
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('LEFTPADDING', (0,0), (-1,-1), 0),
        ('RIGHTPADDING', (0,0), (-1,-1), 0),
    ]))
    
    elementos.append(header_master)
    elementos.append(Spacer(1, 10))

    # --- 2. Título ---
    elementos.append(Paragraph("COMUNICADO", style_title))

    # --- 3. Corpo do Texto ---
    data_fim_formatada = comunicado.data_fim.strftime('%d de %B de %Y') if comunicado.data_fim else "30 de Março de 2025"
    
    texto_corpo = f"""
    Comunica-se a todos os Departamentos de Ensino e Investigação, período Regular e Pós-laboral, 
    que estão abertas as inscrições para o Trabalho de Fim de Curso, no período de {comunicado.data_inicio.day} a {data_fim_formatada}.<br/><br/>
    Para tal, são requisitos necessários os seguintes:<br/>
    • Cópia colorida do B.I e actualizada;<br/>
    • Requerimento dirigido ao Presidente do Instituto Superior Politécnico do Bié;<br/>
    • Curriculum Académico;<br/>
    • Ficha de Reconfirmação de Matricula do ano em curso;<br/><br/>
    Os estudantes finalistas dos anos lectivos anteriores poderão pagar uma taxa de inscrição de {comunicado.taxa_finalistas_antigos:,.2f} AOA 
    e ficam isentos da taxa de emolumentos os estudantes finalistas do ano lectivo transato a luz do decreto Presidencial nº124/20 de 04 de Maio.<br/><br/>
    Todos os finalistas dos Cursos Pós-Laboral, devem pagar {comunicado.taxa_pos_laboral_tfc:,.2f} AOA para a conclusão do Trabalho de Fim de Curso (TFC) 
    e {comunicado.taxa_pos_laboral_exame:,.2f} AOA para a realização do Exame de Estado.
    """
    elementos.append(Paragraph(texto_corpo, style_body))

    # Observação
    obs_text = f"<b>OBS:.</b> Todos finalistas que reúnam os requisitos acima poderão passar pelo Departamento em referência a partir da data da Publicação do presente comunicado no período compreendido entre as {comunicado.hora_inicio.strftime('%H:%M')} às {comunicado.hora_fim.strftime('%H:%M')} horas."
    elementos.append(Paragraph(obs_text, style_body))

    # Local e Data
    data_extenso = comunicado.data_publicacao.strftime("%d de %B de %Y") if comunicado.data_publicacao else "26 de Fevereiro de 2025"
    elementos.append(Spacer(1, 5))
    elementos.append(Paragraph(f"Departamento de Investigação Científica, Inovação Empreendedorismo e Pós-Graduação do Instituto Superior Politécnico do Bié, no Cuito, aos {data_extenso}.", style_body))

    # --- 4. Assinatura ---
    elementos.append(Spacer(1, 15))
    assinatura_chefe = [
        [Paragraph("<b>A Chefe do Departamento de Investigação Científica</b>", style_header)],
        [Spacer(1, 12)],
        [Paragraph("___________________________", style_header)],
        [Paragraph("<b>Ana Angelina Cangombe</b>", style_header)],
    ]
    tab_chefe = Table(assinatura_chefe, colWidths=[10*cm])
    tab_chefe.setStyle(TableStyle([('ALIGN', (0,0), (-1,-1), 'CENTER')]))
    elementos.append(tab_chefe)

    # --- 5. Rodapé Fixo ---
    elementos.append(Spacer(1, 10))
    elementos.append(HRFlowable(width="100%", thickness=0.5, color=colors.black))
    footer_text = """
    Rua Padre Fidalgo entre Artur de Paiva e Francisco de Leite Cardoso S/N, Cidade do Cuito-Bié<br/>
    E-mail: ispb.bie@gmail.com | NIF: 5000308765 | Telefone: 922408061 | http://isp-bie.ao/ 
    """
    elementos.append(Paragraph(footer_text, style_footer_text))

    # Construção do PDF
    doc.build(elementos)
    buffer.seek(0)

    response = HttpResponse(buffer, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="Comunicado_{comunicado.id}.pdf"'
    return response
