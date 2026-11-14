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
