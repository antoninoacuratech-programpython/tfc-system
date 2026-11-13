"""Controlo de acesso por perfil de utilizador.

Uso:

    @perfil_requerido(*PERFIS_GESTAO)
    def minha_view(request): ...

O decorador já inclui ``login_required``: utilizadores anónimos são
redireccionados para o login e utilizadores sem o perfil adequado recebem
uma página 403.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

PERFIL_COORDENACAO = "cordenacao"
PERFIL_PRESIDENTE = "presidente"
PERFIL_AREA_CIENTIFICA = "area_cientifica"
PERFIL_AREA_ETICA = "area_etica"
PERFIL_DAC = "dac"
PERFIL_TUTOR = "tutor"
PERFIL_ESTUDANTE = "estudante"

# Perfis que utilizam o painel de gestão (admin/base.html).
PERFIS_GESTAO = (
    PERFIL_COORDENACAO,
    PERFIL_PRESIDENTE,
    PERFIL_AREA_CIENTIFICA,
    PERFIL_AREA_ETICA,
    PERFIL_DAC,
)


def tem_perfil(user, *perfis):
    """True se o utilizador estiver autenticado e tiver um dos perfis (superuser passa sempre)."""
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.perfil in perfis


def perfil_requerido(*perfis):
    """Restringe a view a utilizadores autenticados com um dos perfis indicados."""

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not tem_perfil(request.user, *perfis):
                raise PermissionDenied("Não tem permissão para aceder a esta página.")
            return view_func(request, *args, **kwargs)

        return login_required(_wrapped)

    return decorator


def garantir_acesso_estudante(user, estudante):
    """Um estudante só acede aos seus próprios documentos; os restantes perfis acedem a todos."""
    if user.perfil == PERFIL_ESTUDANTE and not user.is_superuser and user.pk != estudante.pk:
        raise PermissionDenied("Só pode aceder aos seus próprios documentos.")
