"""Declaração do orientador com assinatura digital, visto científico e verificação pública."""

import io
import os
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.staticfiles import finders
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .. import assinatura as ass
from ..models import DocumentoAssinado, NotificacaoFinal, Tema, Usuario
from ..permissions import PERFIL_AREA_CIENTIFICA, PERFIL_ESTUDANTE, PERFIL_TUTOR, PERFIS_GESTAO, perfil_requerido, tem_perfil

MESES = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto",
         "Setembro", "Outubro", "Novembro", "Dezembro"]


def _tema_do_estudante(estudante):
    return Tema.objects.select_related("tutor_indicado", "estudante__curso").filter(
        estudante=estudante, status_tutor="aprovado"
    ).last()


def _documento_valido(tema):
    return tema.documentos_assinados.filter(anulado_em__isnull=True).select_related("assinante", "visto_por").first()


def _nome(u):
    return f"{u.nome} {u.sobrenome}" if u else ""


# --- PDF -----------------------------------------------------------------------

def _rubrica_img(usuario, largura=5 * cm, altura=1.6 * cm):
    png = ass.rubrica_de(usuario) if usuario else None
    if not png:
        return Spacer(1, altura)
    img = Image(io.BytesIO(png))
    escala = min(largura / img.imageWidth, altura / img.imageHeight)
    img.drawWidth, img.drawHeight = img.imageWidth * escala, img.imageHeight * escala
    img.hAlign = "CENTER"
    return img


def _qr(url, lado=2.6 * cm):
    codigo = qr.QrCodeWidget(url)
    x1, y1, x2, y2 = codigo.getBounds()
    desenho = Drawing(lado, lado, transform=[lado / (x2 - x1), 0, 0, lado / (y2 - y1), 0, 0])
    desenho.add(codigo)
    return desenho


def pdf_declaracao(request, tema, documento=None):
    estudante, orientador = tema.estudante, tema.tutor_indicado
    nome_curso = str(estudante.curso.nome).upper() if estudante.curso else "ENGENHARIA INFORMÁTICA"
    depto = getattr(estudante, "depart", None) or (estudante.curso.departamento if estudante.curso else None)
    nome_depto = str(depto.nome).strip() if depto else "Engenharias"
    # alguns departamentos já estão gravados como "Departamento de ..."
    if nome_depto.lower().startswith("departamento de "):
        nome_depto = nome_depto[len("departamento de "):]
    nome_depto = nome_depto.strip().capitalize()

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=50, leftMargin=50, topMargin=40, bottomMargin=40,
                            title="Declaração de responsabilidade do orientador", author=_nome(orientador))
    el = []

    st_inst = ParagraphStyle("Inst", fontSize=10, fontName="Helvetica-Bold", leading=12, alignment=TA_CENTER)
    st_dept = ParagraphStyle("Dept", fontSize=9, fontName="Helvetica-Bold", leading=11, alignment=TA_CENTER, textColor=colors.gray)
    st_titulo = ParagraphStyle("Titulo", fontSize=12, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceBefore=20, spaceAfter=20)
    st_corpo = ParagraphStyle("Corpo", fontSize=11, fontName="Helvetica", leading=16, alignment=TA_JUSTIFY)
    st_centro = ParagraphStyle("Centro", fontSize=10.5, fontName="Helvetica", leading=14, alignment=TA_CENTER)
    st_nome = ParagraphStyle("Nome", fontSize=10.5, fontName="Helvetica-Bold", leading=13, alignment=TA_CENTER)
    st_selo = ParagraphStyle("Selo", fontSize=7.5, leading=9.5, alignment=TA_CENTER, textColor=colors.HexColor("#1e3a8a"))
    st_verif = ParagraphStyle("Verif", fontSize=8, leading=11, alignment=TA_LEFT, textColor=colors.HexColor("#334155"))

    logo_path = finders.find("imgs/icons/finalispbie.jpg")
    logo = Image(logo_path, width=2.2 * cm, height=2.2 * cm) if logo_path and os.path.exists(logo_path) else Paragraph("<b>ISPB</b>", st_inst)
    el.append(Table([[logo, [
        Paragraph("REPÚBLICA DE ANGOLA", st_inst),
        Paragraph("MINISTÉRIO DO ENSINO SUPERIOR, CIÊNCIA, TECNOLOGIA E INOVAÇÃO", st_inst),
        Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", st_inst),
        Paragraph(f"DEPARTAMENTO DE {nome_depto.upper()}", st_dept),
        Paragraph(f"CURSO DE {nome_curso}", st_dept),
    ]]], colWidths=[2.5 * cm, 13.5 * cm]))
    el.append(Spacer(1, 5))
    el.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    el.append(Paragraph("DECLARAÇÃO DE RESPONSABILIDADE DO (A) ORIENTADOR (A)", st_titulo))

    el.append(Paragraph(
        f"Para os devidos efeitos, eu, docente do Departamento de {nome_depto}, orientador (a) do "
        f"trabalho de Fim de Curso do (a) estudante <b>{_nome(estudante).upper()}</b>, do Instituto Superior "
        f"Politécnico do Bié, com o tema: <u>{tema.titulo}</u>.<br/><br/>Por este meio confirmo que o trabalho em "
        f"referência se encontra concluído e que o estudante está preparado para assumir a sua defesa pública.",
        st_corpo))
    el.append(Spacer(1, 20))

    dia = timezone.localtime(documento.assinado_em).date() if documento else date.today()
    el.append(Paragraph(f"Cuito, aos {dia.day} de {MESES[dia.month - 1]} de {dia.year}",
                        ParagraphStyle("Data", alignment=TA_RIGHT, fontSize=11)))
    el.append(Spacer(1, 30))

    # visto (esquerda) e orientador (direita), linha a linha para ficarem alinhados
    visto = documento.visto_por if documento and documento.visto_em else None
    linha = Paragraph("_" * 38, st_inst)
    data_visto = f"{timezone.localtime(documento.visto_em):%d/%m/%Y}" if visto else "______/_________/20___"
    linhas = [
        [Paragraph(f"VISTO<br/>{data_visto}", st_centro), ""],
        [Paragraph("O Vice-Presidente P/Assuntos Científicos", st_centro), Paragraph("O orientador (a)", st_centro)],
        [_rubrica_img(visto) if visto else Spacer(1, 1.6 * cm), _rubrica_img(orientador) if documento else Spacer(1, 1.6 * cm)],
        [linha, linha],
        [Paragraph(_nome(visto), st_nome) if visto else "", Paragraph(_nome(orientador) or "", st_nome)],
        [Paragraph(f"Visto digital em {timezone.localtime(documento.visto_em):%d/%m/%Y %H:%M}", st_selo) if visto else "",
         Paragraph(f"Assinado digitalmente em {timezone.localtime(documento.assinado_em):%d/%m/%Y %H:%M}", st_selo) if documento else ""],
    ]
    tabela = Table(linhas, colWidths=[8 * cm, 8 * cm])
    tabela.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 14),
        ("TOPPADDING", (0, 3), (-1, 3), 0), ("BOTTOMPADDING", (0, 2), (-1, 2), 0),
    ]))
    el.append(tabela)
    el.append(Spacer(1, 26))

    if documento:
        url = request.build_absolute_uri(reverse("verificar_documento", args=[documento.codigo]))
        caixa = Table([[_qr(url), Paragraph(
            f"<b>Documento assinado digitalmente no SGTF</b><br/>"
            f"Código de verificação: <b>{documento.codigo}</b><br/>"
            f"Para confirmar a autenticidade, leia o QR code ou abra:<br/><font color='#1d4ed8'>{url}</font><br/>"
            f"<font size='6.5' color='#64748b'>SHA-256: {documento.impressao}</font>", st_verif)]],
            colWidths=[3 * cm, 13 * cm])
        caixa.setStyle(TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#93c5fd")),
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8), ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        el.append(caixa)
    else:
        el.append(Paragraph("Versão não assinada — gerada para consulta.",
                            ParagraphStyle("Rasc", fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor("#b91c1c"))))
    el.append(Spacer(1, 14))
    el.append(Paragraph("Rua Padre Fidalgo entre Artur de Paiva e Francisco de Leite Cardoso S/N, Cidade do Cuito-Bié",
                        ParagraphStyle("Rod", fontSize=7, alignment=TA_CENTER, textColor=colors.grey)))
    doc.build(el)
    return buffer.getvalue()


def _pode_ver(user, tema):
    if user.is_superuser or tem_perfil(user, *PERFIS_GESTAO):
        return True
    if user.perfil == PERFIL_TUTOR and tema.tutor_indicado_id == user.pk:
        return True
    return user.perfil == PERFIL_ESTUDANTE and tema.estudante_id == user.pk


@login_required
def gerar_pdf_declaracao_orientador(request, usuario_id):
    estudante = get_object_or_404(Usuario, pk=usuario_id, perfil="estudante")
    tema = _tema_do_estudante(estudante)
    if not tema:
        messages.error(request, "Não foi encontrado um tema aprovado para este estudante.")
        return redirect("lista_estudantes_tutor" if request.user.perfil == PERFIL_TUTOR else "login")
    if not _pode_ver(request.user, tema):
        raise PermissionDenied("Não tem permissão para ver esta declaração.")

    documento = _documento_valido(tema)
    resposta = HttpResponse(pdf_declaracao(request, tema, documento), content_type="application/pdf")
    nome = f"declaracao-orientador-{documento.codigo if documento else 'nao-assinada'}.pdf"
    resposta["Content-Disposition"] = f'inline; filename="{nome}"'
    return resposta


# --- assinar (tutor) -------------------------------------------------------------

def _aplicar_rubrica(request):
    """Guarda a rubrica nova, se veio no pedido; exige que exista uma no fim."""
    png = ass.rubrica_do_pedido(request)
    if png:
        ass.guardar_rubrica(request.user, png)
    elif not ass.rubrica_de(request.user):
        raise ass.ErroAssinatura("Desenhe ou carregue a sua rubrica antes de assinar.")


@perfil_requerido(PERFIL_TUTOR)
def assinar_declaracao(request, usuario_id):
    estudante = get_object_or_404(Usuario, pk=usuario_id, perfil="estudante")
    tema = _tema_do_estudante(estudante)
    if not tema or tema.tutor_indicado_id != request.user.pk:
        raise PermissionDenied("Só o orientador deste estudante pode assinar a declaração.")
    documento = _documento_valido(tema)

    if request.method == "POST" and not documento:
        try:
            ass.confirmar_senha(request)
            with transaction.atomic():
                _aplicar_rubrica(request)
                documento = ass.assinar_declaracao(tema, request.user)
        except ass.ErroAssinatura as erro:
            messages.error(request, str(erro))
            return redirect("assinar_declaracao", estudante.pk)

        link = reverse("gerar_pdf_declaracao", args=[estudante.pk])
        NotificacaoFinal.objects.create(usuario=estudante, titulo="Declaração do orientador assinada",
                                        mensagem=f"{_nome(request.user)} assinou a sua declaração de responsabilidade.", link=link)
        for u in Usuario.objects.filter(perfil=PERFIL_AREA_CIENTIFICA, estado_user="activo"):
            NotificacaoFinal.objects.create(usuario=u, titulo="Declaração para visto",
                                            mensagem=f"Declaração do orientador de {_nome(estudante)} aguarda o seu visto.",
                                            link=reverse("vistos_declaracoes"))
        messages.success(request, f"Declaração assinada. Código de verificação: {documento.codigo}")
        return redirect("assinar_declaracao", estudante.pk)

    return render(request, "assinaturas/assinar.html", {
        "estudante": estudante, "tema": tema, "documento": documento,
        "tem_rubrica": bool(ass.rubrica_de(request.user)),
    })


@perfil_requerido(PERFIL_TUTOR)
@require_POST
def anular_assinatura(request, documento_id):
    documento = get_object_or_404(DocumentoAssinado, pk=documento_id, assinante=request.user, anulado_em__isnull=True)
    documento.anulado_em = timezone.now()
    documento.save(update_fields=["anulado_em"])
    messages.success(request, "Assinatura anulada. O código deixa de ser válido e pode assinar de novo.")
    return redirect("assinar_declaracao", documento.tema.estudante_id)


# --- visto (área científica) ---------------------------------------------------

@perfil_requerido(PERFIL_AREA_CIENTIFICA)
def vistos_declaracoes(request):
    documentos = DocumentoAssinado.objects.filter(anulado_em__isnull=True).select_related(
        "tema__estudante__curso", "assinante", "visto_por")
    return render(request, "assinaturas/vistos.html", {
        "pendentes": [d for d in documentos if not d.visto_em],
        "concluidos": [d for d in documentos if d.visto_em][:30],
        "tem_rubrica": bool(ass.rubrica_de(request.user)),
    })


@perfil_requerido(PERFIL_AREA_CIENTIFICA)
@require_POST
def dar_visto(request, documento_id):
    try:
        ass.confirmar_senha(request)
        with transaction.atomic():
            documento = get_object_or_404(DocumentoAssinado.objects.select_for_update(),
                                          pk=documento_id, anulado_em__isnull=True, visto_em__isnull=True)
            _aplicar_rubrica(request)
            documento.visto_por, documento.visto_em = request.user, timezone.now()
            documento.save(update_fields=["visto_por", "visto_em"])
    except ass.ErroAssinatura as erro:
        messages.error(request, str(erro))
        return redirect("vistos_declaracoes")

    tema = documento.tema
    for destino in (tema.estudante, documento.assinante):
        NotificacaoFinal.objects.create(usuario=destino, titulo="Visto dado na declaração",
                                        mensagem=f"A Área Científica deu o visto na declaração de {_nome(tema.estudante)}.",
                                        link=reverse("gerar_pdf_declaracao", args=[tema.estudante_id]))
    messages.success(request, "Visto aplicado à declaração.")
    return redirect("vistos_declaracoes")


# --- rubrica e verificação ----------------------------------------------------

@login_required
def minha_rubrica(request):
    png = ass.rubrica_de(request.user)
    if not png:
        raise Http404
    resposta = HttpResponse(png, content_type="image/png")
    resposta["Cache-Control"] = "private, no-cache"
    return resposta


def verificar_documento(request, codigo=None):
    codigo = (codigo or request.GET.get("codigo", "")).strip().upper()
    documento = None
    if codigo:
        documento = DocumentoAssinado.objects.select_related(
            "tema__estudante__curso", "assinante", "visto_por").filter(codigo=codigo).first()
    return render(request, "assinaturas/verificar.html", {
        "codigo": codigo,
        "documento": documento,
        "integro": ass.integro(documento) if documento else False,
    })
