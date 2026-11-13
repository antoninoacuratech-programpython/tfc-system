from django.conf import settings
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path, re_path
from django.views.decorators.cache import never_cache
from django.views.static import serve

admin.site.site_header = f"{settings.SISTEMA_NOME} · Administração"
admin.site.site_title = settings.SISTEMA_NOME
admin.site.index_title = settings.SISTEMA_DESCRICAO


@never_cache
def saude(request):
    """Verificação de estado usada pelo UptimeRobot / GitHub Actions para manter o site acordado.

    Não consulta a base de dados, para não gastar horas de computação da Neon.
    """
    return JsonResponse({"estado": "ok", "sistema": settings.SISTEMA_NOME})


urlpatterns = [
    path("saude/", saude, name="saude"),
    path("admin/", admin.site.urls),
    path("", include("Coordenacao.urls")),
    path("chat/", include("chat.urls")),
]

if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
