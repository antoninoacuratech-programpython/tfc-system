"""Importação de estudantes a partir da exportação do sistema de gestão escolar (CSV ou Excel).

As contas são criadas já activas, com uma senha temporária que o estudante
troca no primeiro acesso.
"""

import csv
import io
import re
import secrets
import unicodedata

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction

MAX_LINHAS = 2000
TAMANHO_MAX = 5 * 1024 * 1024
ALFABETO_SENHA = "abcdefghijkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

# nomes de coluna aceites (sem acentos, minúsculas, sem espaços)
COLUNAS = {
    "nome": {"nome", "nomes", "primeironome", "firstname", "name"},
    "sobrenome": {"sobrenome", "apelido", "apelidos", "ultimonome", "lastname", "surname"},
    "nome_completo": {"nomecompleto", "nomedoestudante", "nomedoaluno", "estudante", "aluno", "fullname"},
    "email": {"email", "e-mail", "correio", "correioeletronico", "correioelectronico", "mail"},
    "telefone": {"telefone", "telemovel", "contacto", "contato", "celular", "phone", "tel"},
    "numero": {"numero", "numeroestudante", "numerodeestudante", "nestudante", "nºestudante", "n.ºestudante",
               "matricula", "numeromatricula", "numerodematricula", "nmatricula", "ndematricula",
               "processo", "numeroprocesso", "numerodeprocesso", "nprocesso", "ndeprocesso",
               "ndeestudante", "numerodoestudante", "codigo", "id",
               "nº", "n.º", "nº de processo", "n.º de processo", "nº processo", "nº de matrícula",
               "n.º de matrícula", "nº matrícula", "nº de estudante", "n.º de estudante", "nº do estudante"},
    "curso": {"curso", "course"},
}


class ErroImportacao(Exception):
    pass


def _chave(texto):
    texto = unicodedata.normalize("NFKD", str(texto or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[\s_.º°]+", "", texto)


def _mapear_colunas(cabecalho):
    mapa = {}
    for i, titulo in enumerate(cabecalho):
        k = _chave(titulo)
        for campo, aliases in COLUNAS.items():
            if campo not in mapa and (k in {_chave(a) for a in aliases}):
                mapa[campo] = i
    if "email" not in mapa:
        raise ErroImportacao("O ficheiro não tem a coluna de e-mail. Use o modelo disponível nesta página.")
    if "nome" not in mapa and "nome_completo" not in mapa:
        raise ErroImportacao("O ficheiro não tem a coluna do nome (ou «nome completo»).")
    return mapa


def _linhas_csv(dados):
    for codificacao in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            texto = dados.decode(codificacao)
            break
        except UnicodeDecodeError:
            continue
    try:
        dialecto = csv.Sniffer().sniff(texto[:4096], delimiters=";,\t")
    except csv.Error:
        class dialecto(csv.excel):
            delimiter = ";" if texto.count(";") > texto.count(",") else ","
    return [linha for linha in csv.reader(io.StringIO(texto), dialecto)]


def _linhas_excel(dados):
    from openpyxl import load_workbook
    try:
        livro = load_workbook(io.BytesIO(dados), read_only=True, data_only=True)
    except Exception:
        raise ErroImportacao("Não foi possível abrir o ficheiro Excel. Guarde-o como .xlsx e tente de novo.")
    folha = livro.worksheets[0]
    linhas = [["" if c is None else str(c).strip() for c in linha] for linha in folha.iter_rows(values_only=True)]
    livro.close()
    return linhas


def ler_ficheiro(upload):
    if not upload:
        raise ErroImportacao("Escolha o ficheiro exportado do sistema de gestão escolar.")
    if upload.size > TAMANHO_MAX:
        raise ErroImportacao("O ficheiro excede 5 MB.")
    nome = upload.name.lower()
    dados = upload.read()
    if nome.endswith(".xlsx"):
        linhas = _linhas_excel(dados)
    elif nome.endswith((".csv", ".txt")):
        linhas = _linhas_csv(dados)
    else:
        raise ErroImportacao("Formato não suportado. Use CSV ou Excel (.xlsx).")

    linhas = [l for l in linhas if any(str(c).strip() for c in l)]
    if len(linhas) < 2:
        raise ErroImportacao("O ficheiro está vazio ou só tem o cabeçalho.")
    if len(linhas) - 1 > MAX_LINHAS:
        raise ErroImportacao(f"No máximo {MAX_LINHAS} estudantes por importação.")

    mapa = _mapear_colunas(linhas[0])

    def valor(linha, campo):
        i = mapa.get(campo)
        return str(linha[i]).strip() if i is not None and i < len(linha) else ""

    registos = []
    for n, linha in enumerate(linhas[1:], start=2):
        nome, sobrenome = valor(linha, "nome"), valor(linha, "sobrenome")
        if not nome and valor(linha, "nome_completo"):
            partes = valor(linha, "nome_completo").split()
            nome, sobrenome = partes[0], " ".join(partes[1:])
        elif nome and not sobrenome and " " in nome and "sobrenome" not in mapa:
            nome, sobrenome = nome.split(" ", 1)
        numero = valor(linha, "numero")
        if numero.endswith(".0"):  # números lidos do Excel como decimais
            numero = numero[:-2]
        telefone = re.sub(r"\D", "", valor(linha, "telefone"))[-9:]
        registos.append({
            "linha": n,
            "nome": nome.title()[:100],
            "sobrenome": sobrenome.title()[:100],
            "email": valor(linha, "email").lower(),
            "telefone": telefone,
            "numero": numero[:30],
            "curso_nome": valor(linha, "curso"),
        })
    return registos


def _curso_por_nome(nome, cursos):
    k = _chave(nome)
    return next((c for c in cursos if _chave(c.nome) == k), None)


def analisar(registos, curso_padrao, cursos_permitidos, usar_coluna_curso=False):
    """Marca cada registo como «novo», «existe» ou «erro» (com o motivo)."""
    from .models import Usuario

    emails = {r["email"] for r in registos if r["email"]}
    existentes = set(Usuario.objects.filter(email__in=emails).values_list("email", flat=True))
    numeros = {r["numero"] for r in registos if r["numero"]}
    numeros_existentes = set(Usuario.objects.filter(numero_estudante__in=numeros).exclude(numero_estudante="")
                             .values_list("numero_estudante", flat=True))
    cursos = list(cursos_permitidos)
    vistos = set()

    for r in registos:
        curso = curso_padrao
        if usar_coluna_curso and r["curso_nome"]:
            curso = _curso_por_nome(r["curso_nome"], cursos)
        r["curso_id"] = curso.pk if curso else None
        r["curso"] = curso.nome if curso else r["curso_nome"]
        r["estado"], r["motivo"] = "novo", ""
        try:
            validate_email(r["email"])
        except ValidationError:
            r["estado"], r["motivo"] = "erro", "E-mail em falta ou inválido"
            continue
        if not r["nome"]:
            r["estado"], r["motivo"] = "erro", "Nome em falta"
        elif not curso:
            r["estado"], r["motivo"] = "erro", f"Curso «{r['curso_nome']}» desconhecido ou não permitido"
        elif r["email"] in vistos:
            r["estado"], r["motivo"] = "erro", "E-mail repetido no ficheiro"
        elif r["email"] in existentes:
            r["estado"], r["motivo"] = "existe", "Já tem conta no sistema"
        elif r["numero"] and r["numero"] in numeros_existentes:
            r["estado"], r["motivo"] = "existe", "Número de estudante já registado"
        vistos.add(r["email"])
    return registos


def senha_temporaria():
    while True:
        senha = "".join(secrets.choice(ALFABETO_SENHA) for _ in range(10))
        if any(c.isdigit() for c in senha) and any(c.isupper() for c in senha):
            return senha


@transaction.atomic
def criar_contas(registos):
    """Cria as contas dos registos «novo». Devolve [(registo, senha temporária)]."""
    from .models import Curso, Usuario

    cursos = {c.pk: c for c in Curso.objects.select_related("departamento")}
    criados = []
    for r in registos:
        if r.get("estado") != "novo" or Usuario.objects.filter(email=r["email"]).exists():
            continue
        curso = cursos.get(r["curso_id"])
        senha = senha_temporaria()
        Usuario.objects.create_user(
            email=r["email"], password=senha, nome=r["nome"], sobrenome=r["sobrenome"],
            telefone=r["telefone"], perfil="estudante", estado_user="activo",
            curso=curso, depart=curso.departamento if curso else None,
            numero_estudante=r["numero"], deve_mudar_senha=True,
        )
        criados.append((r, senha))
    return criados


MODELO_CSV = (
    "numero_estudante;nome;sobrenome;email;telefone\n"
    "20230145;Antonino;Calado Jacob Teodoro;antonino.teodoro@ispb.ao;923000000\n"
)
