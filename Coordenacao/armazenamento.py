"""Armazenamento dos uploads na própria base de dados.

O disco da Render gratuita é apagado a cada reinício, por isso os ficheiros
vivem na tabela Coordenacao_ficheiro (na Neon) em vez da pasta media/.
"""

import mimetypes
import posixpath

from django.core.files.base import ContentFile
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


def _modelo():
    from .models import Ficheiro
    return Ficheiro


def _normalizar(nome):
    return posixpath.normpath(str(nome).replace("\\", "/")).lstrip("/")


@deconstructible
class BaseDadosStorage(Storage):
    def _open(self, name, mode="rb"):
        registo = _modelo().objects.filter(nome=_normalizar(name)).only("conteudo").first()
        if registo is None:
            raise FileNotFoundError(name)
        return ContentFile(bytes(registo.conteudo), name=name)

    def _save(self, name, content):
        name = _normalizar(name)
        if hasattr(content, "seek"):
            content.seek(0)
        dados = b"".join(content.chunks()) if hasattr(content, "chunks") else content.read()
        if isinstance(dados, str):
            dados = dados.encode("utf-8")
        # o tipo enviado pelo navegador não é de confiança; vale a extensão
        tipo = mimetypes.guess_type(name)[0] or "application/octet-stream"
        _modelo().objects.update_or_create(
            nome=name, defaults={"conteudo": dados, "tamanho": len(dados), "tipo": tipo[:100]}
        )
        return name

    def exists(self, name):
        return _modelo().objects.filter(nome=_normalizar(name)).exists()

    def delete(self, name):
        if name:
            _modelo().objects.filter(nome=_normalizar(name)).delete()

    def size(self, name):
        registo = _modelo().objects.filter(nome=_normalizar(name)).only("tamanho").first()
        if registo is None:
            raise FileNotFoundError(name)
        return registo.tamanho

    def url(self, name):
        return reverse("ficheiro", args=[_normalizar(name)])

    def listdir(self, path):
        prefixo = _normalizar(path).rstrip("/") + "/" if _normalizar(path) not in ("", ".") else ""
        pastas, ficheiros = set(), []
        for nome in _modelo().objects.filter(nome__startswith=prefixo).values_list("nome", flat=True):
            resto = nome[len(prefixo):]
            if "/" in resto:
                pastas.add(resto.split("/", 1)[0])
            else:
                ficheiros.append(resto)
        return sorted(pastas), ficheiros

    def get_created_time(self, name):
        return _modelo().objects.only("criado_em").get(nome=_normalizar(name)).criado_em

    get_modified_time = get_created_time
