from .progresso import alertas_do_dia


class AlertasProgressoMiddleware:
    """Gera os alertas de progresso uma vez por dia, no primeiro pedido de um utilizador autenticado.

    Assim os avisos saem mesmo sem cron no servidor (a Render gratuita não tem).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            alertas_do_dia()
        return self.get_response(request)


SESSAO_PERFIL = "perfil_ativo"


class PerfilAtivoMiddleware:
    """Aplica o perfil escolhido na sessão a quem acumula funções (ex.: coordenador e tutor)."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and user.is_authenticated:
            ativo = request.session.get(SESSAO_PERFIL)
            if ativo and ativo != user.perfil and not user.ativar_perfil(ativo):
                # o perfil foi retirado entretanto: volta ao principal
                request.session.pop(SESSAO_PERFIL, None)
        return self.get_response(request)
