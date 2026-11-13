"""Filtros de template partilhados pelos layouts do SGTF."""

from django import template

register = template.Library()

ROTULOS_PERFIL = {
    "cordenacao": "Coordenação",
    "dac": "DAC",
    "presidente": "Presidência",
    "estudante": "Estudante",
    "area_cientifica": "Área Científica",
    "tutor": "Tutor / Orientador",
    "area_etica": "Área Ética",
}


@register.filter
def rotulo_perfil(user):
    if getattr(user, "is_superuser", False) and not getattr(user, "perfil", ""):
        return "Administrador"
    return ROTULOS_PERFIL.get(getattr(user, "perfil", ""), "Utilizador")


@register.filter
def iniciais(user):
    nome = (getattr(user, "nome", "") or "").strip()
    sobrenome = (getattr(user, "sobrenome", "") or "").strip()
    letras = (nome[:1] + (sobrenome.split()[-1][:1] if sobrenome else "")).upper()
    return letras or "U"
