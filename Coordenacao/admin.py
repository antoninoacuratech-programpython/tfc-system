from django.contrib import admin
from . models import Departamento
admin.site.register(Departamento)
from .models import PerfilAdicional  # noqa: E402


@admin.register(PerfilAdicional)
class PerfilAdicionalAdmin(admin.ModelAdmin):
    list_display = ("usuario", "perfil", "criado_em")
    list_filter = ("perfil",)
    search_fields = ("usuario__nome", "usuario__sobrenome", "usuario__email")
