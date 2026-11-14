"""Comparação de temas (TF-IDF) e sugestão de tutor, sem serviços externos."""

import math
import re
import unicodedata
from collections import Counter

PARADAS = set("""
a ao aos as com como da das de do dos e em entre era essa esse esta este estas estes eu foi for
ha isso isto ja la mais mas me mesmo meu muito na nas nao no nos o os ou para pela pelas pelo
pelos por qual quando que quem se sem ser seu sua suas seus so sobre tambem te tem um uma umas uns
caso estudo estudos atraves visando visa partir base uso usando utilizando proposta propor
""".split())


def _sem_acentos(texto):
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _radical(palavra):
    for fim in ("coes", "cao", "mente", "idade", "ais", "eis", "oes", "es", "s"):
        if palavra.endswith(fim) and len(palavra) - len(fim) >= 4:
            return palavra[: -len(fim)]
    return palavra


def tokens(texto):
    texto = _sem_acentos((texto or "").lower())
    return [_radical(p) for p in re.findall(r"[a-z0-9]{3,}", texto) if p not in PARADAS]


def _texto_tema(titulo, descricao):
    # o título conta a dobrar: é o que melhor identifica o tema
    return tokens(titulo) * 2 + tokens(descricao)


class _Indice:
    def __init__(self, documentos):
        self.n = len(documentos) + 1
        df = Counter()
        for doc in documentos:
            df.update(set(doc))
        self.idf = {t: math.log((self.n + 1) / (c + 1)) + 1 for t, c in df.items()}

    def vetor(self, doc):
        tf = Counter(doc)
        v = {t: (1 + math.log(c)) * self.idf.get(t, math.log(self.n + 1) + 1) for t, c in tf.items()}
        norma = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norma for t, x in v.items()}

    @staticmethod
    def cosseno(a, b):
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(t, 0.0) for t, x in a.items())


def _corpus(excluir_estudante_id=None):
    from .models import Tema, TemaSugerido

    itens = []
    temas = Tema.objects.select_related("estudante", "estudante__curso", "tutor_indicado")
    if excluir_estudante_id:
        temas = temas.exclude(estudante_id=excluir_estudante_id)
    for t in temas:
        itens.append({
            "tipo": "tema",
            "titulo": t.titulo,
            "autor": f"{t.estudante.nome} {t.estudante.sobrenome}",
            "curso": t.estudante.curso.nome.strip() if t.estudante.curso else "",
            "ano": t.data_envio.year if t.data_envio else None,
            "estado": t.get_status_final_display(),
            "tutor_id": t.tutor_indicado_id,
            "tokens": _texto_tema(t.titulo, t.descricao),
        })
    for s in TemaSugerido.objects.select_related("curso").filter(tema__isnull=True):
        itens.append({
            "tipo": "sugestao",
            "titulo": s.titulo,
            "autor": "Sugestão da coordenação",
            "curso": s.curso.nome.strip(),
            "ano": s.criado_em.year,
            "estado": "Sugerido",
            "tutor_id": s.tutor_sugerido_id,
            "tokens": _texto_tema(s.titulo, s.descricao),
        })
    return itens


def temas_semelhantes(titulo, descricao, excluir_estudante_id=None, limite=5, minimo=0.30):
    novo = _texto_tema(titulo, descricao)
    if len(novo) < 3:
        return []
    corpus = _corpus(excluir_estudante_id)
    if not corpus:
        return []
    indice = _Indice([c["tokens"] for c in corpus])
    v = indice.vetor(novo)
    resultados = []
    for c in corpus:
        s = indice.cosseno(v, indice.vetor(c["tokens"]))
        if s >= minimo:
            resultados.append({
                "titulo": c["titulo"], "autor": c["autor"], "curso": c["curso"], "ano": c["ano"],
                "estado": c["estado"], "tipo": c["tipo"], "percentagem": round(s * 100),
            })
    resultados.sort(key=lambda r: r["percentagem"], reverse=True)
    return resultados[:limite]


def sugerir_tutores(titulo, descricao, limite=3):
    from .models import Tema, Usuario

    tutores = list(Usuario.objects.filter(perfil="tutor", estado_user="activo"))
    if not tutores:
        return []
    corpus = _corpus()
    indice = _Indice([c["tokens"] for c in corpus] or [[]])
    v = indice.vetor(_texto_tema(titulo, descricao))

    carga = Counter(
        Tema.objects.filter(tutor_indicado__isnull=False).exclude(status_final="rejeitado")
        .exclude(status_tutor="rejeitado").values_list("tutor_indicado_id", flat=True)
    )
    maior_carga = max(carga.values(), default=0)

    sugestoes = []
    for tutor in tutores:
        temas_dele = [c for c in corpus if c["tutor_id"] == tutor.pk and c["tipo"] == "tema"]
        sims = sorted((indice.cosseno(v, indice.vetor(c["tokens"])) for c in temas_dele), reverse=True)
        afinidade = sims[0] if sims else 0.0
        parecidos = sum(1 for s in sims if s >= 0.25)
        n = carga.get(tutor.pk, 0)
        disponibilidade = 1 - (n / (maior_carga + 1))
        pontuacao = 0.7 * afinidade + 0.3 * disponibilidade

        motivos = []
        if parecidos:
            motivos.append(f"orientou {parecidos} tema{'s' if parecidos > 1 else ''} parecido{'s' if parecidos > 1 else ''}")
        motivos.append("sem orientandos neste momento" if n == 0 else f"{n} orientando{'s' if n > 1 else ''} ativo{'s' if n > 1 else ''}")
        sugestoes.append({
            "id": tutor.pk, "nome": f"{tutor.nome} {tutor.sobrenome}",
            "pontuacao": round(pontuacao * 100), "motivo": "; ".join(motivos),
        })
    sugestoes.sort(key=lambda s: s["pontuacao"], reverse=True)
    return sugestoes[:limite]
