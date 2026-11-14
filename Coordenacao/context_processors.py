from django.conf import settings

from .models import NotificacaoFinal


def notificacoes_usuario(request):
    if request.user.is_authenticated:
        notificacoes = NotificacaoFinal.objects.filter(usuario=request.user).order_by("-criada_em")
        return {
            "notificacoes_sistema": notificacoes[:5],
            "total_notificacoes": notificacoes.filter(lida=False).count(),
        }
    return {"notificacoes_sistema": [], "total_notificacoes": 0}


def perfis(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {}
    from .templatetags.sgtf import ROTULOS_PERFIL
    disponiveis = user.perfis_disponiveis
    if len(disponiveis) < 2:
        return {}
    return {"outros_perfis": [(p, ROTULOS_PERFIL.get(p, p)) for p in disponiveis if p != user.perfil]}


def instituicao(request):
    return {
        "INSTITUICAO_NOME": settings.INSTITUICAO_NOME,
        "INSTITUICAO_SIGLA": settings.INSTITUICAO_SIGLA,
        "SISTEMA_NOME": settings.SISTEMA_NOME,
        "SISTEMA_DESCRICAO": settings.SISTEMA_DESCRICAO,
        "IA_DISPONIVEL": bool(settings.ANTHROPIC_API_KEY),
    }
