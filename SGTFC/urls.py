from django.conf import settings
from django.contrib import admin
from django.urls import include, path, re_path
from django.views.static import serve

admin.site.site_header = f"{settings.SISTEMA_NOME} · Administração"
admin.site.site_title = settings.SISTEMA_NOME
admin.site.index_title = settings.SISTEMA_DESCRICAO

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("Coordenacao.urls")),
    path("chat/", include("chat.urls")),
]

if settings.SERVE_MEDIA:
    urlpatterns += [
        re_path(r"^media/(?P<path>.*)$", serve, {"document_root": settings.MEDIA_ROOT}),
    ]
