"""Assistente de IA do SGTF (Claude, via SDK oficial da Anthropic)."""

import base64
import json
import logging

from django.conf import settings

logger = logging.getLogger(__name__)

LIMITE_PALAVRAS_DESCRICAO = 250
TAMANHO_MAXIMO_PDF = 20 * 1024 * 1024


class ErroIA(Exception):
    """Erro com mensagem pronta a mostrar ao utilizador."""


def ia_disponivel():
    return bool(settings.ANTHROPIC_API_KEY)


def _cliente():
    import anthropic  # importado aqui para o resto do sistema funcionar mesmo sem o pacote

    return anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY, timeout=90.0, max_retries=2)


def _pedir_json(system, conteudo, schema, effort="medium"):
    if not ia_disponivel():
        raise ErroIA("O assistente de IA ainda não está configurado neste servidor.")

    import anthropic

    try:
        resposta = _cliente().beta.messages.create(
            model=settings.IA_MODELO,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": conteudo}],
            output_config={"effort": effort, "format": {"type": "json_schema", "schema": schema}},
            # se o modelo recusar, a API tenta automaticamente outro modelo adequado
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.AuthenticationError:
        logger.error("Chave da API Anthropic inválida")
        raise ErroIA("O assistente de IA está mal configurado (chave inválida). Avise o administrador.")
    except anthropic.RateLimitError:
        raise ErroIA("O assistente está muito ocupado neste momento. Tente dentro de um minuto.")
    except anthropic.APIStatusError as e:
        logger.error("Erro da API Anthropic %s: %s", e.status_code, e.message)
        raise ErroIA("O assistente de IA não respondeu como esperado. Tente novamente.")
    except anthropic.APIConnectionError:
        raise ErroIA("Não foi possível contactar o assistente de IA. Verifique a ligação e tente novamente.")

    if resposta.stop_reason == "refusal":
        raise ErroIA("O assistente não pode ajudar com este pedido. Reformule a ideia e tente de novo.")
    if resposta.stop_reason == "max_tokens":
        raise ErroIA("A resposta do assistente ficou incompleta. Tente com um texto mais curto.")

    texto = next((b.text for b in resposta.content if b.type == "text"), "")
    try:
        return json.loads(texto)
    except json.JSONDecodeError:
        logger.error("Resposta da IA sem JSON válido: %r", texto[:300])
        raise ErroIA("O assistente devolveu uma resposta inválida. Tente novamente.")


def _contar_palavras(texto):
    return len(texto.split())


SCHEMA_PROPOSTA = {
    "type": "object",
    "properties": {
        "titulo": {"type": "string"},
        "problema": {"type": "string"},
        "objetivo_geral": {"type": "string"},
        "objetivos_especificos": {"type": "array", "items": {"type": "string"}},
        "metodologia": {"type": "string"},
        "palavras_chave": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["titulo", "problema", "objetivo_geral", "objetivos_especificos", "metodologia", "palavras_chave"],
    "additionalProperties": False,
}

SYSTEM_PROPOSTA = """És um orientador académico experiente do Instituto Superior Politécnico do Bié (Angola).
Ajudas estudantes finalistas a estruturar a PROPOSTA do Trabalho de Fim de Curso (TFC) a partir de uma ideia curta.

Regras:
- Escreve em português de Angola/Portugal (não brasileiro), em linguagem académica clara.
- Não escrevas o trabalho: só organizas a proposta para o estudante rever e o tutor avaliar.
- Mantém-te fiel à ideia do estudante; não inventes dados, números ou resultados.
- Título: específico, até 20 palavras, indicando o quê, para quê e onde (se a ideia o disser).
- Problema: 2 a 3 frases. Objetivo geral: 1 frase começada por verbo no infinitivo.
- Objetivos específicos: 3 a 4, curtos, cada um começado por verbo no infinitivo.
- Metodologia: 2 frases (abordagem, técnicas ou ferramentas, forma de validação).
- No total, problema + objetivos + metodologia não podem passar de 200 palavras.
- Palavras-chave: 3 a 5."""


def assistente_proposta(ideia, curso=""):
    ideia = (ideia or "").strip()
    if len(ideia) < 15:
        raise ErroIA("Descreva a sua ideia com um pouco mais de detalhe (pelo menos uma frase).")
    pedido = f"Curso do estudante: {curso or 'não indicado'}\n\nIdeia do estudante:\n{ideia[:3000]}"
    dados = _pedir_json(SYSTEM_PROPOSTA, pedido, SCHEMA_PROPOSTA)

    objetivos = "\n".join(f"- {o.strip()}" for o in dados["objetivos_especificos"] if o.strip())
    descricao = (
        f"Problema: {dados['problema'].strip()}\n\n"
        f"Objetivo geral: {dados['objetivo_geral'].strip()}\n\n"
        f"Objetivos específicos:\n{objetivos}\n\n"
        f"Metodologia: {dados['metodologia'].strip()}"
    )
    # o formulário aceita no máximo 250 palavras: corta a metodologia se for preciso
    if _contar_palavras(descricao) > LIMITE_PALAVRAS_DESCRICAO:
        palavras = descricao.split()
        descricao = " ".join(palavras[:LIMITE_PALAVRAS_DESCRICAO - 1]) + "…"
    return {
        "titulo": dados["titulo"].strip(),
        "descricao": descricao,
        "palavras_chave": [p.strip() for p in dados["palavras_chave"] if p.strip()][:5],
    }


SCHEMA_RESUMO = {
    "type": "object",
    "properties": {
        "sintese": {"type": "string"},
        "objetivos": {"type": "array", "items": {"type": "string"}},
        "metodologia": {"type": "string"},
        "contributos": {"type": "array", "items": {"type": "string"}},
        "pontos_de_atencao": {"type": "array", "items": {"type": "string"}},
        "perguntas_sugeridas": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["sintese", "objetivos", "metodologia", "contributos", "pontos_de_atencao", "perguntas_sugeridas"],
    "additionalProperties": False,
}

SYSTEM_RESUMO = """Preparas fichas de leitura para membros do júri de pré-defesas de Trabalhos de Fim de Curso
no Instituto Superior Politécnico do Bié (Angola). Escreve em português de Angola/Portugal.

A ficha cabe numa página A4:
- Síntese: um parágrafo de 4 a 6 frases sobre o que o trabalho propõe.
- Objetivos: 2 a 4 itens. Metodologia: 2 a 3 frases.
- Contributos: 2 a 3 itens. Pontos de atenção: 2 a 4 (lacunas, riscos, aspetos a verificar).
- Perguntas sugeridas: 3 a 5 perguntas objetivas que o júri pode fazer ao estudante.
Baseia-te só no material fornecido; se faltar informação, indica-o nos pontos de atenção em vez de inventar."""


def resumo_para_juri(tema):
    blocos = []
    if tema.resumo and tema.resumo.name.lower().endswith(".pdf"):
        try:
            if tema.resumo.size <= TAMANHO_MAXIMO_PDF:
                with tema.resumo.open("rb") as f:
                    dados = base64.standard_b64encode(f.read()).decode("ascii")
                blocos.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": dados}})
        except (OSError, ValueError):
            logger.warning("Não foi possível ler o PDF do tema %s", tema.pk)

    estudante = tema.estudante
    tutor = tema.tutor_indicado
    texto = (
        f"Título: {tema.titulo}\n"
        f"Estudante: {estudante.nome} {estudante.sobrenome}\n"
        f"Curso: {estudante.curso.nome if estudante.curso else '—'}\n"
        f"Orientador: {(tutor.nome + ' ' + tutor.sobrenome) if tutor else '—'}\n\n"
        f"Descrição submetida pelo estudante:\n{tema.descricao}\n\n"
        + ("O PDF anexado é o resumo do trabalho." if blocos else "Não há PDF do trabalho; usa apenas a descrição acima.")
    )
    blocos.append({"type": "text", "text": texto})
    resultado = _pedir_json(SYSTEM_RESUMO, blocos, SCHEMA_RESUMO)
    resultado["fonte"] = "pdf" if len(blocos) > 1 else "descricao"
    return resultado
