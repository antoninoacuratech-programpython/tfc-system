import io, os
from django.http import HttpResponse
from django.conf import settings
from django.contrib.staticfiles import finders
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import Image
from reportlab.lib.units import cm


def campo(valor, tamanho=60):
    """
    Se houver valor, mostra o valor.
    Se não houver, mostra linha para preenchimento manual.
    """
    if valor:
        return valor
    return "_" * tamanho


def gerar_ficha_tfc_pdf(dados: dict):

    buffer = io.BytesIO()

    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=50
    )

    elements = []

    # ================= ESTILOS =================
    style_header = ParagraphStyle(
        'Header', fontSize=10, fontName='Helvetica-Bold',
        alignment=TA_CENTER, leading=14
    )

    style_subheader = ParagraphStyle(
        'SubHeader', fontSize=9, fontName='Helvetica-Bold',
        alignment=TA_CENTER, leading=12
    )

    style_title = ParagraphStyle(
        'Title', fontSize=11, fontName='Helvetica-Bold',
        alignment=TA_CENTER, spaceBefore=10, spaceAfter=15
    )

    style_text = ParagraphStyle(
        'Text', fontSize=10, leading=15
    )

    style_sign = ParagraphStyle(
        'Sign', fontSize=10, alignment=TA_CENTER
    )

    # ================= LOGO =================
    relative_path = 'imgs/icons/finalispbie.jpg'
    logo_path = finders.find(relative_path) or os.path.join(settings.STATIC_ROOT, relative_path)

    try:
        logo = Image(logo_path, width=2.2 * cm, height=2.2 * cm)
    except:
        logo = Paragraph("ISPB", style_header)

    # ================= CABEÇALHO =================
    header_text = [
        Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_header),
        Paragraph(
            "DEPARTAMENTO DE INVESTIGAÇÃO CIENTÍFICA, INOVAÇÃO, "
            "EMPREENDEDORISMO E PÓS-GRADUAÇÃO",
            style_subheader
        ),
    ]

    header_table = Table([[logo, header_text]], colWidths=[2.8 * cm, 13.2 * cm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('ALIGN', (0, 0), (0, 0), 'CENTER'),
    ]))

    elements.append(header_table)
    elements.append(Spacer(1, 20))

    # ================= TÍTULO =================
    elements.append(Paragraph(
        "FICHA DE INSCRIÇÃO DO TRABALHO DE FIM DE CURSO Nº ____________.",
        style_title
    ))

    # ================= CORPO DINÂMICO =================
    elements.append(Paragraph(
        f"Nome completo: {campo(dados.get('nome'), 75)};",
        style_text
    ))

    elements.append(Paragraph(
        f"Curso: {campo(dados.get('curso'), 35)}, "
        f"Período: {dados.get('periodo', 'regular        Pós-Laboral')}",
        style_text
    ))

    elements.append(Paragraph(
        f"Departamento: {campo(dados.get('departamento'), 30)}, "
        f"Nº universitário: {campo(dados.get('numero'), 15)};",
        style_text
    ))

    elements.append(Paragraph(
        f"Ano Académico: {campo(dados.get('ano'), 10)}; "
        f"Nacionalidade: {campo(dados.get('nacionalidade'), 20)},",
        style_text
    ))

    elements.append(Paragraph(
        f"Endereço: {campo(dados.get('endereco'), 30)} "
        f"Telefone: {campo(dados.get('telefone'), 25)};",
        style_text
    ))

    elements.append(Paragraph(
        f"Email: {campo(dados.get('email'), 45)}, "
        f"Ano de conclusão do Plano Curricular: {campo(dados.get('ano_conclusao'), 10)};",
        style_text
    ))

    elements.append(Spacer(1, 10))

    elements.append(Paragraph(
        f"Título do trabalho de fim de curso: {campo(dados.get('titulo'), 70)}",
        style_text
    ))

    elements.append(Paragraph(
        "_" * 95 + ";",
        style_text
    ))

    elements.append(Spacer(1, 5))

    elements.append(Paragraph(
        f"Local onde o trabalho será desenvolvido: {campo(dados.get('local'), 60)};",
        style_text
    ))

    elements.append(Paragraph(
        f"Orientador: {campo(dados.get('orientador'), 30)}; "
        f"DEI{campo('', 35)};",
        style_text
    ))

    elements.append(Paragraph(
        f"Co-orientador: {campo(dados.get('coorientador'), 25)}; "
        f"DEI{campo('', 30)}.",
        style_text
    ))

    elements.append(Spacer(1, 20))

    elements.append(Paragraph(
        "Cuito, aos ______/_______/_________.",
        style_text
    ))

    # ================= ASSINATURAS =================
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("Conferido por:", style_text))
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("_________________________________________", style_sign))
    elements.append(Paragraph("(Nome Completo e legível)", style_sign))

    elements.append(Spacer(1, 25))
    elements.append(Paragraph("O estudante", style_text))
    elements.append(Spacer(1, 25))
    elements.append(Paragraph("__________________________________", style_sign))
    elements.append(Paragraph("(Nome Completo e legível)", style_sign))

    # ================= BUILD =================
    doc.build(elements)
    buffer.seek(0)

    return HttpResponse(buffer, content_type="application/pdf")
   