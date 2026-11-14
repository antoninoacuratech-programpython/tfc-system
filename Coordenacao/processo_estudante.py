"""Processo completo de um estudante: tudo o que o sistema sabe sobre ele, num só sítio.

Usado pela página «Processo do estudante» e pelo ZIP que a coordenação descarrega.
"""

import inspect
import io
import logging
import posixpath
import re
import unicodedata
import zipfile

from django.utils import timezone

logger = logging.getLogger(__name__)


def _limpo(texto, maximo=60):
    texto = unicodedata.normalize("NFKD", str(texto)).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^A-Za-z0-9._-]+", "_", texto).strip("_")
    return texto[:maximo] or "documento"


def _relacao(obj, nome):
    try:
        return getattr(obj, nome)
    except Exception:  # OneToOne inexistente
        return None


def recolher(estudante):
    """Junta os dados do processo e a lista de documentos (carregados e gerados)."""
    from .models import DocumentoAssinado, PlanoTrabalho, Recomendacao
    from .progresso import resumo as resumo_progresso

    temas = list(estudante.temas.select_related("tutor_indicado", "processo").order_by("data_envio"))
    tema = next((t for t in reversed(temas) if t.status_final == "aprovado"), temas[-1] if temas else None)
    inscricoes = list(estudante.inscricoes_tfc.select_related("tema", "aprovado_por").order_by("data_criacao"))
    predefesas = list(estudante.minhas_predefesas.select_related(
        "tema", "presidente", "secretario", "primeiro_vogal", "segundo_vogal").order_by("data", "hora"))
    for p in predefesas:
        p.despacho = _relacao(p, "despacho_vinculado")
        p.solicitacao = _relacao(p, "solicitacao_defesa")
        p.acta = _relacao(p.solicitacao, "acta_final") if p.solicitacao else None

    plano = PlanoTrabalho.objects.filter(tema=tema).prefetch_related("etapas").first() if tema else None
    recomendacoes = list(Recomendacao.objects.filter(tema__estudante=estudante)
                         .select_related("autor", "tutor", "predefesa").order_by("data_criacao"))
    assinaturas = list(DocumentoAssinado.objects.filter(tema__estudante=estudante).select_related("assinante", "visto_por"))

    documentos = []

    def ficheiro(pasta, nome, campo):
        if campo and campo.name:
            documentos.append({"pasta": pasta, "nome": nome, "url": campo.url, "campo": campo,
                               "extensao": posixpath.splitext(campo.name)[1].lower() or ".bin"})

    def gerado(pasta, nome, url, gerar):
        documentos.append({"pasta": pasta, "nome": nome, "url": url, "gerar": gerar, "extensao": ".pdf"})

    from django.urls import reverse
    from .views import assinaturas as v_ass
    from .views import defesas as v_def
    from .views import despachos as v_desp
    from .views import inscricoes as v_insc
    from .views import predefesas as v_pre
    from .views import recomendacoes as v_rec

    for t in temas:
        sufixo = f" ({t.data_envio:%d-%m-%Y})" if len(temas) > 1 and t.data_envio else ""
        ficheiro("02_Tema", f"Resumo do tema{sufixo}", t.resumo)
        ficheiro("02_Tema", f"Requerimento do tema{sufixo}", t.requerimento)

    for i in inscricoes:
        gerado("03_Inscricao", "Ficha de inscricao", reverse("baixar_pdf_tfc", args=[i.pk]), (v_insc.baixar_pdf_tfc, i.pk))
        ficheiro("03_Inscricao", "Requerimento", i.requerimento)
        ficheiro("03_Inscricao", "Curriculo academico", i.curriculum_academico)
        ficheiro("03_Inscricao", "Ficha de reconfirmacao", i.ficha_reconfirmacao)
        ficheiro("03_Inscricao", "Comprovativo de pagamento", i.comprovativo_pagamento)
        ficheiro("03_Inscricao", "Copia do BI", i.copia_bi)

    if plano:
        for e in plano.etapas.all():
            ficheiro("04_Progresso", f"Etapa {e.ordem} - {e.titulo}", e.ficheiro)

    for n, p in enumerate(predefesas, 1):
        pasta = "05_Predefesa" if len(predefesas) == 1 else f"05_Predefesa_{n}"
        gerado(pasta, "Convocatoria da pre-defesa", reverse("pdf_predefesa", args=[p.pk]), (v_pre.gerar_pdf_predefesa, p.pk))
        if p.despacho:
            gerado(pasta, "Despacho", reverse("gerar_despacho_pdf", args=[p.despacho.pk]), (v_desp.gerar_despacho_pdf, p.despacho.pk))
        if p.solicitacao:
            gerado("06_Defesa", "Solicitacao de defesa", reverse("gerar_pdf_solicitacao", args=[p.solicitacao.pk]),
                   (v_def.gerar_pdf_solicitacao, p.solicitacao.pk))
        if p.acta:
            gerado("06_Defesa", f"Acta de defesa {p.acta.numero_acta}", reverse("baixar_acta_pdf", args=[p.acta.pk]),
                   (v_def.baixar_acta_pdf, p.acta.pk))

    if recomendacoes:
        gerado("07_Recomendacoes", "Recomendacoes", reverse("baixar_recomendacoes", args=[estudante.pk]),
               (v_rec.baixar_recomendacoes_pdf, estudante.pk))
    if tema and tema.status_tutor == "aprovado":
        gerado("08_Declaracao", "Declaracao do orientador", reverse("gerar_pdf_declaracao", args=[estudante.pk]),
               (v_ass.gerar_pdf_declaracao_orientador, estudante.pk))

    return {
        "estudante": estudante,
        "temas": temas,
        "tema": tema,
        "inscricoes": inscricoes,
        "plano": plano,
        "etapas": list(plano.etapas.all()) if plano else [],
        "progresso": resumo_progresso(plano),
        "predefesas": predefesas,
        "recomendacoes": recomendacoes,
        "melhorias": [r for r in recomendacoes if r.tipo == "melhoria"],
        "cumpridas": sum(1 for r in recomendacoes if r.tipo == "melhoria" and r.estado == "cumprida"),
        "assinaturas": assinaturas,
        "documentos": documentos,
    }


def _conteudo_gerado(request, gerar):
    vista, arg = gerar
    resposta = inspect.unwrap(vista)(request, arg)  # sem os decoradores: a permissão já foi verificada
    if getattr(resposta, "status_code", 200) != 200:
        raise ValueError(f"resposta {resposta.status_code}")
    if getattr(resposta, "streaming", False):
        return b"".join(resposta.streaming_content)
    return resposta.content


def pdf_resumo(dados):
    """Folha de rosto do processo, em PDF."""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    e = dados["estudante"]
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.8 * cm, rightMargin=1.8 * cm, topMargin=1.6 * cm, bottomMargin=1.6 * cm,
                            title=f"Processo de {e.nome} {e.sobrenome}")
    h1 = ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=16, leading=20, textColor=colors.HexColor("#0f172a"))
    h2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=11, leading=14, spaceBefore=12, spaceAfter=4, textColor=colors.HexColor("#1d4ed8"))
    txt = ParagraphStyle("t", fontName="Helvetica", fontSize=9, leading=12)
    peq = ParagraphStyle("p", fontName="Helvetica", fontSize=8, leading=10, textColor=colors.HexColor("#64748b"))

    def tabela(linhas, larguras=(4.5 * cm, 12.9 * cm)):
        t = Table([[Paragraph(f"<b>{a}</b>", txt), Paragraph(str(b or "—"), txt)] for a, b in linhas], colWidths=larguras)
        t.setStyle(TableStyle([("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#e2e8f0")),
                               ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f8fafc")),
                               ("VALIGN", (0, 0), (-1, -1), "TOP")]))
        return t

    el = [Paragraph("Processo do estudante", h1),
          Paragraph(f"Gerado pelo SGTF em {timezone.localtime():%d/%m/%Y %H:%M}", peq), Spacer(1, 8)]
    el.append(Paragraph("Dados do estudante", h2))
    el.append(tabela([("Nome", f"{e.nome} {e.sobrenome}"), ("E-mail", e.email), ("Telefone", e.telefone),
                      ("Curso", e.curso.nome if e.curso else ""), ("Estado da conta", e.estado_user)]))

    tema = dados["tema"]
    if tema:
        el.append(Paragraph("Tema", h2))
        el.append(tabela([
            ("Título", tema.titulo), ("Processo", tema.processo.titulo if tema.processo else ""),
            ("Orientador", f"{tema.tutor_indicado.nome} {tema.tutor_indicado.sobrenome}" if tema.tutor_indicado else ""),
            ("Parecer do tutor", tema.get_status_tutor_display()), ("Parecer da coordenação", tema.get_status_coordenacao_display()),
            ("Estado final", tema.get_status_final_display()),
            ("Submetido em", f"{tema.data_envio:%d/%m/%Y}" if tema.data_envio else ""),
        ]))

    for i in dados["inscricoes"]:
        el.append(Paragraph("Inscrição do TFC", h2))
        el.append(tabela([("Estado", i.get_status_display()), ("Período", i.periodo),
                          ("Local de desenvolvimento", i.local_desenvolvimento), ("Data", f"{i.data_criacao:%d/%m/%Y}")]))

    prog = dados["progresso"]
    if dados["etapas"]:
        el.append(Paragraph(f"Progresso do trabalho — {prog['aprovadas']}/{prog['total']} etapas ({prog['percentagem']}%) · {prog['rotulo']}", h2))
        el.append(tabela([(f"{x.ordem}. {x.titulo}", f"{x.get_estado_display()} · prazo {x.prazo:%d/%m/%Y}") for x in dados["etapas"]]))

    for p in dados["predefesas"]:
        el.append(Paragraph(f"Pré-defesa de {p.data:%d/%m/%Y} às {p.hora:%H:%M}", h2))
        linhas = [(f, f"{d.nome} {d.sobrenome}" if d else "") for f, _, d in p.mesa()]
        linhas.append(("Resultado", p.get_resultado_display() if p.resultado else "Sessão por encerrar"))
        if p.despacho:
            linhas.append(("Despacho", f"{p.despacho.numero_despacho} · {p.despacho.get_status_display()}"))
        if p.solicitacao:
            linhas.append(("Defesa", f"{p.solicitacao.data_defesa:%d/%m/%Y} às {p.solicitacao.hora_defesa:%H:%M}"))
        if p.acta:
            linhas.append(("Acta", f"{p.acta.numero_acta} · avaliação final {p.acta.avaliacao_final}"))
        el.append(tabela(linhas))

    if dados["melhorias"]:
        el.append(Paragraph(f"Recomendações a cumprir — {dados['cumpridas']} de {len(dados['melhorias'])} cumpridas", h2))
        el.append(tabela([(r.funcao_autor or "Orientador", f"{r.texto} <font color='#64748b'>[{r.get_estado_display()}]</font>")
                          for r in dados["melhorias"]]))

    if dados["documentos"]:
        el.append(Paragraph("Documentos incluídos neste ZIP", h2))
        el.append(tabela([(d["pasta"], d["nome"]) for d in dados["documentos"]]))
    doc.build(el)
    return buf.getvalue()


def gerar_zip(request, dados):
    """Devolve (bytes do ZIP, lista de avisos sobre documentos que não puderam ser incluídos)."""
    avisos, usados = [], set()
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("00_Resumo_do_processo.pdf", pdf_resumo(dados))
        for d in dados["documentos"]:
            caminho = f"{d['pasta']}/{_limpo(d['nome'])}{d['extensao']}"
            n = 2
            while caminho in usados:
                caminho = f"{d['pasta']}/{_limpo(d['nome'])}_{n}{d['extensao']}"
                n += 1
            try:
                if "campo" in d:
                    with d["campo"].open("rb") as f:
                        conteudo = f.read()
                else:
                    conteudo = _conteudo_gerado(request, d["gerar"])
            except Exception as erro:  # ficheiro perdido ou PDF que falhou: regista e continua
                logger.warning("Processo %s: %s não incluído (%s)", dados["estudante"].pk, caminho, erro)
                avisos.append(f"{d['pasta']} / {d['nome']}: não foi possível incluir ({erro.__class__.__name__}).")
                continue
            usados.add(caminho)
            zf.writestr(caminho, conteudo)
        if avisos:
            zf.writestr("LEIA-ME_documentos_em_falta.txt",
                        "Os seguintes documentos não puderam ser incluídos:\n\n" + "\n".join(avisos) + "\n")
    return buf.getvalue(), avisos


def nome_zip(estudante):
    return f"Processo_{_limpo(estudante.nome + '_' + estudante.sobrenome, 40)}_{timezone.localdate():%Y%m%d}.zip"
