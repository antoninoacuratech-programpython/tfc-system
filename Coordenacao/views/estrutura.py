"""Departamentos e cursos."""

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from ..models import Curso, Departamento
from ..permissions import PERFIS_GESTAO, perfil_requerido


@perfil_requerido(*PERFIS_GESTAO)
def lista_departamentos(request):
    if not request.user.is_staff:
        messages.error(request, "Acesso não autorizado.")
        return redirect("admink")

    departamentos = Departamento.objects.all().order_by("nome")
    return render(request, "departamentos/lista.html", {
        "departamentos": departamentos
    })


@perfil_requerido(*PERFIS_GESTAO)
def criar_departamento(request):
    if not request.user.is_staff:
        messages.error(request, "Acesso não autorizado.")
        return redirect("admink")

    if request.method == "POST":
        nome = request.POST.get("nome")
        descricao = request.POST.get("descricao")

        if not nome:
            messages.error(request, "O nome é obrigatório.")
        else:
            Departamento.objects.create(
                nome=nome,
                descricao=descricao
            )
            messages.success(request, "Departamento criado com sucesso.")
            return redirect("lista_departamentos")

    return render(request, "departamentos/form.html")


@perfil_requerido(*PERFIS_GESTAO)
def editar_departamento(request, id):
    if not request.user.is_staff:
        messages.error(request, "Acesso não autorizado.")
        return redirect("admink")

    departamento = get_object_or_404(Departamento, id=id)

    if request.method == "POST":
        departamento.nome = request.POST.get("nome")
        departamento.descricao = request.POST.get("descricao")
        departamento.save()

        messages.success(request, "Departamento atualizado com sucesso.")
        return redirect("lista_departamentos")

    return render(request, "departamentos/form.html", {
        "departamento": departamento
    })


@perfil_requerido(*PERFIS_GESTAO)
def excluir_departamento(request, id):
    if not request.user.is_staff:
        messages.error(request, "Acesso não autorizado.")
        return redirect("admink")

    departamento = get_object_or_404(Departamento, id=id)

    try:
        departamento.delete()
        messages.success(request, "Departamento excluído com sucesso.")
    except:
        messages.error(request, "Não é possível excluir um departamento com cursos associados.")

    return redirect("lista_departamentos")


@perfil_requerido(*PERFIS_GESTAO)
def lista_cursos(request):
    if not request.user.is_staff:
        messages.error(request, "Acesso não autorizado.")
        return redirect("admink")

    cursos = Curso.objects.select_related("departamento").all().order_by("nome")
    return render(request, "cursos/lista.html", {
        "cursos": cursos
    })


@perfil_requerido(*PERFIS_GESTAO)
def criar_curso(request):
    if not request.user.is_staff:
        messages.error(request, "Acesso não autorizado.")
        return redirect("admink")

    departamentos = Departamento.objects.all()

    if request.method == "POST":
        nome = request.POST.get("nome")
        descricao = request.POST.get("descricao")
        departamento_id = request.POST.get("departamento")

        if not nome or not departamento_id:
            messages.error(request, "Preencha todos os campos obrigatórios.")
        else:
            Curso.objects.create(
                nome=nome,
                descricao=descricao,
                departamento_id=departamento_id
            )
            messages.success(request, "Curso criado com sucesso.")
            return redirect("lista_cursos")

    return render(request, "cursos/form.html", {
        "departamentos": departamentos
    })


@perfil_requerido(*PERFIS_GESTAO)
def editar_curso(request, id):
    if not request.user.is_staff:
        messages.error(request, "Acesso não autorizado.")
        return redirect("admink")

    curso = get_object_or_404(Curso, id=id)
    departamentos = Departamento.objects.all()

    if request.method == "POST":
        curso.nome = request.POST.get("nome")
        curso.descricao = request.POST.get("descricao")
        curso.departamento_id = request.POST.get("departamento")
        curso.save()

        messages.success(request, "Curso atualizado com sucesso.")
        return redirect("lista_cursos")

    return render(request, "cursos/form.html", {
        "curso": curso,
        "departamentos": departamentos
    })


@perfil_requerido(*PERFIS_GESTAO)
def excluir_curso(request, id):
    # Permissão: apenas presidente ou staff
    if not request.user.is_staff:
        messages.error(request, "Acesso não autorizado.")
        return redirect("admink")

    curso = get_object_or_404(Curso, id=id)

    curso.delete()
    messages.success(request, "Curso excluído com sucesso.")

    return redirect("lista_cursos")
