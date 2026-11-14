"""Assinatura digital de documentos do SGTF.

Cada documento assinado tem um código único e a impressão SHA-256 do seu
conteúdo. O QR code no PDF leva à página pública de verificação, que volta a
calcular a impressão: se alguém alterar o tema ou os nomes depois da
assinatura, a verificação deixa de bater certo.
"""

import base64
import binascii
import hashlib
import io
import secrets

from django.core.cache import cache
from django.utils import timezone

ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # sem 0/O e 1/I para não haver confusões
TAMANHO_MAX_RUBRICA = 2 * 1024 * 1024
TENTATIVAS_SENHA = 5


class ErroAssinatura(Exception):
    pass


def gerar_codigo():
    from .models import DocumentoAssinado
    while True:
        bruto = "".join(secrets.choice(ALFABETO) for _ in range(12))
        codigo = f"{bruto[:4]}-{bruto[4:8]}-{bruto[8:]}"
        if not DocumentoAssinado.objects.filter(codigo=codigo).exists():
            return codigo


def conteudo_declaracao(tema):
    estudante, orientador = tema.estudante, tema.tutor_indicado
    return "\n".join([
        "declaracao_orientador",
        f"estudante:{estudante.pk}:{estudante.nome} {estudante.sobrenome}",
        f"tema:{tema.pk}:{tema.titulo}",
        f"orientador:{orientador.pk if orientador else ''}:{orientador.nome + ' ' + orientador.sobrenome if orientador else ''}",
    ])


def calcular_impressao(documento):
    base = f"{documento.codigo}\n{documento.assinado_em.isoformat()}\n{conteudo_declaracao(documento.tema)}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def integro(documento):
    return secrets.compare_digest(documento.impressao, calcular_impressao(documento))


def limpar_rubrica(dados):
    """Valida a imagem da rubrica e devolve um PNG transparente, recortado e com tamanho controlado."""
    from PIL import Image, UnidentifiedImageError

    if not dados or len(dados) > TAMANHO_MAX_RUBRICA:
        raise ErroAssinatura("A imagem da rubrica está vazia ou é demasiado grande (máx. 2 MB).")
    try:
        img = Image.open(io.BytesIO(dados))
        img.load()
    except (UnidentifiedImageError, OSError):
        raise ErroAssinatura("Não foi possível ler a imagem da rubrica. Use PNG ou JPG.")
    if img.width * img.height > 16_000_000:
        raise ErroAssinatura("A imagem da rubrica é demasiado grande.")

    img = img.convert("RGBA")
    # fundo claro passa a transparente e o traço fica azul-escuro, como uma caneta
    pixels = []
    for r, g, b, a in img.getdata():
        claro = (r + g + b) / 3
        if a < 40 or claro > 200:
            pixels.append((0, 0, 0, 0))
        else:
            pixels.append((20, 35, 90, min(255, int(a * (1 - claro / 255) * 1.6) + 60)))
    img.putdata(pixels)

    caixa = img.getbbox()
    if not caixa:
        raise ErroAssinatura("A rubrica está em branco.")
    img = img.crop(caixa)
    img.thumbnail((900, 300))
    saida = io.BytesIO()
    img.save(saida, format="PNG", optimize=True)
    return saida.getvalue()


def rubrica_do_pedido(request):
    """Lê a rubrica desenhada (data URL) ou carregada. Devolve bytes PNG ou None."""
    desenho = request.POST.get("rubrica_desenho", "")
    if desenho.startswith("data:image/png;base64,"):
        try:
            return limpar_rubrica(base64.b64decode(desenho.split(",", 1)[1], validate=True))
        except (binascii.Error, ValueError):
            raise ErroAssinatura("O desenho da rubrica chegou incompleto. Tente de novo.")
    ficheiro = request.FILES.get("rubrica_ficheiro")
    if ficheiro:
        if ficheiro.size > TAMANHO_MAX_RUBRICA:
            raise ErroAssinatura("A imagem da rubrica excede 2 MB.")
        return limpar_rubrica(ficheiro.read())
    return None


def guardar_rubrica(usuario, png):
    from .models import Rubrica
    Rubrica.objects.update_or_create(usuario=usuario, defaults={"imagem": png})


def rubrica_de(usuario):
    from .models import Rubrica
    registo = Rubrica.objects.filter(usuario=usuario).first()
    return bytes(registo.imagem) if registo else None


def confirmar_senha(request):
    """Confirma a identidade de quem assina. Bloqueia 15 minutos após 5 tentativas erradas."""
    chave = f"assinatura-falhas:{request.user.pk}"
    falhas = cache.get(chave, 0)
    if falhas >= TENTATIVAS_SENHA:
        raise ErroAssinatura("Demasiadas tentativas com a senha errada. Aguarde 15 minutos.")
    if not request.user.check_password(request.POST.get("senha", "")):
        cache.set(chave, falhas + 1, 15 * 60)
        raise ErroAssinatura("Senha incorrecta. A assinatura não foi aplicada.")
    cache.delete(chave)


def assinar_declaracao(tema, assinante):
    from .models import DocumentoAssinado
    doc = DocumentoAssinado(tema=tema, assinante=assinante, codigo=gerar_codigo(),
                            assinado_em=timezone.now().replace(microsecond=0))
    doc.impressao = calcular_impressao(doc)
    doc.save()
    return doc
