"""Controlo de acesso por perfil de utilizador."""

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

# perfis que usam o painel de gestão (admin/base.html)
PERFIS_GESTAO = (
    PERFIL_COORDENACAO,
    PERFIL_PRESIDENTE,
    PERFIL_AREA_CIENTIFICA,
    PERFIL_AREA_ETICA,
    PERFIL_DAC,
)


def tem_perfil(user, *perfis):
    if not user.is_authenticated:
        return False
    return user.is_superuser or user.perfil in perfis


def mudar_para_perfil(request, *perfis):
    """Quem acumula funções e abre uma página de outro perfil (p. ex. por uma notificação) muda para ele."""
    from django.contrib import messages

    from .middleware import SESSAO_PERFIL
    from .templatetags.sgtf import ROTULOS_PERFIL

    user = request.user
    if not user.is_authenticated:
        return False
    destino = next((p for p in perfis if p != user.perfil and user.tem_papel(p)), None)
    if not destino:
        return False
    user.ativar_perfil(destino)
    request.session[SESSAO_PERFIL] = destino
    messages.info(request, f"Passou para o perfil {ROTULOS_PERFIL.get(destino, destino)}.")
    return True


def perfil_requerido(*perfis):
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if not tem_perfil(request.user, *perfis) and not mudar_para_perfil(request, *perfis):
                raise PermissionDenied("Não tem permissão para aceder a esta página.")
            return view_func(request, *args, **kwargs)

        return login_required(_wrapped)

    return decorator


def superuser_requerido(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_superuser:
            raise PermissionDenied("Apenas o administrador do sistema pode aceder a esta página.")
        return view_func(request, *args, **kwargs)

    return login_required(_wrapped)


def garantir_acesso_estudante(user, estudante):
    if user.perfil == PERFIL_ESTUDANTE and not user.is_superuser and user.pk != estudante.pk:
        raise PermissionDenied("Só pode aceder aos seus próprios documentos.")
