import io
import os
from datetime import datetime
from django.conf import settings
from django.contrib.staticfiles import finders
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, HRFlowable

def gerar_comunicado_pdf(comunicado, caminho_pdf, logo_path,
                         nome_depto, nome_curso):

    styles = getSampleStyleSheet()

    style_inst_center = ParagraphStyle(
        "inst",
        parent=styles["Normal"],
        alignment=TA_CENTER,
        fontSize=10,
        leading=13,
        spaceAfter=2,
        spaceBefore=2,
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
        spaceBefore=12,
        spaceAfter=12
    )

    doc = SimpleDocTemplate(
        caminho_pdf,
        pagesize=A4,
        rightMargin=2.5*cm,
        leftMargin=2.5*cm,
        topMargin=2.5*cm,
        bottomMargin=2.5*cm
    )

    elementos = []

    try:
        logo = Image(logo_path, width=2.2*cm, height=2.2*cm)
    except:
        logo = Paragraph("<b>ISPB</b>", style_inst_center)

    header_text_content = [
        Paragraph("REPÚBLICA DE ANGOLA", style_inst_center),
        Paragraph(
            "MINISTÉRIO DO ENSINO SUPERIOR, CIÊNCIA, TECNOLOGIA E INOVAÇÃO",
            style_inst_center
        ),
        Paragraph(
            "INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ",
            style_inst_center
        ),
        Paragraph(f"DEPARTAMENTO DE {nome_depto.upper()}",
                  style_dept_center),
        Paragraph(f"CURSO DE {nome_curso.upper()}",
                  style_dept_center),
    ]

    header_table = Table(
        [[logo, header_text_content]],
        colWidths=[3*cm, 13*cm]
    )

    header_table.setStyle(TableStyle([
        ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
        ("ALIGN", (0,0), (0,0), "CENTER"),
        ("LEFTPADDING", (0,0), (-1,-1), 5),
        ("RIGHTPADDING", (0,0), (-1,-1), 5),
        ("TOPPADDING", (0,0), (-1,-1), 5),
        ("BOTTOMPADDING", (0,0), (-1,-1), 5),
    ]))

    elementos.append(header_table)
    elementos.append(Spacer(1, 20))

    elementos.append(
        Paragraph("<b>COMUNICADO</b>",
                  ParagraphStyle(
                      "title",
                      alignment=TA_CENTER,
                      fontSize=14,
                      spaceAfter=20,
                      fontName="Helvetica-Bold"
                  ))
    )

    corpo = texto_comunicado_oficial(comunicado)
    for linha in corpo.split("\n"):
        if linha.strip():
            elementos.append(Paragraph(linha, style_normal))

    elementos.append(Spacer(1, 20))

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

    elementos.append(Spacer(1, 40))
    elementos.append(Paragraph(
        "Rua Padre Fidalgo entre Artur de Paiva e Francisco de Leite Cardoso S/N,"
        " Cidade do Cuito-Bié<br/>"
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
