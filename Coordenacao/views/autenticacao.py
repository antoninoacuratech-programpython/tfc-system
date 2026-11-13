"""Autenticação, registo e perfil do utilizador."""

from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from ..models import Curso, Departamento, Usuario

PAGINA_INICIAL_POR_PERFIL = {
    "cordenacao": "admink",
    "area_cientifica": "index_area_cientifica",
    "estudante": "dashboard_estudante",
    "tutor": "dashboard_tutor",
    "presidente": "dashboard_presidencia",
    "area_etica": "index_area_etica",
}

# só os estudantes se registam sozinhos; os outros perfis são criados pela coordenação
PERFIS_AUTO_REGISTO = ("estudante",)


def pagina_inicial(user):
    if user.is_superuser:
        return "admink"
    return PAGINA_INICIAL_POR_PERFIL.get(user.perfil)


def login_view(request):
    if request.user.is_authenticated:
        if request.user.estado_user != "activo":
            logout(request)
            messages.error(request, "A sua conta está desativada. Contacte a coordenação.")
        elif pagina_inicial(request.user):
            return redirect(pagina_inicial(request.user))

    if request.method == "POST":
        email = (request.POST.get("username") or "").strip().lower()
        password = request.POST.get("senha") or ""
        user = authenticate(request, username=email, password=password)

        if user is None:
            messages.error(request, "E-mail ou senha incorretos.")
        elif user.estado_user != "activo":
            messages.error(request, "A sua conta ainda não está activa. Aguarde a validação da coordenação.")
        elif not pagina_inicial(user):
            messages.error(request, "O seu perfil não tem acesso a nenhum painel. Contacte a coordenação.")
        else:
            auth_login(request, user)
            destino = request.POST.get("next") or request.GET.get("next")
            if destino and url_has_allowed_host_and_scheme(
                destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
            ):
                return redirect(destino)
            return redirect(pagina_inicial(user))

    return render(request, "usuarios/index.html", {"next": request.GET.get("next", "")})


def sair(request):
    logout(request)
    messages.success(request, "Sessão terminada com sucesso.")
    return redirect("login")


def cadastro(request):
    departamentos = Departamento.objects.all()
    cursos = Curso.objects.select_related("departamento").order_by("departamento__nome", "nome")
    contexto = {"departamentos": departamentos, "cursos": cursos}

    if request.method != "POST":
        return render(request, "usuarios/cadastro.html", contexto)

    nome_completo = " ".join(request.POST.get("nome_completo", "").split())
    email = (request.POST.get("email") or "").strip().lower()
    telefone = (request.POST.get("telefone") or "").strip()
    perfil = request.POST.get("perfil")
    password1 = request.POST.get("password1") or ""
    password2 = request.POST.get("password2") or ""
    curso_id = request.POST.get("curso")

    partes = nome_completo.split(" ", 1)
    nome = partes[0]
    sobrenome = partes[1] if len(partes) > 1 else ""

    erros = []
    if not nome:
        erros.append("Indique o seu nome completo.")
    try:
        validate_email(email)
    except ValidationError:
        erros.append("Indique um e-mail válido.")
    if not (telefone.isdigit() and len(telefone) == 9):
        erros.append("O telefone deve ter 9 dígitos.")
    if perfil not in PERFIS_AUTO_REGISTO:
        erros.append("Perfil inválido. Contas de docentes e serviços são criadas pela coordenação.")
    curso = Curso.objects.select_related("departamento").filter(pk=curso_id).first() if curso_id else None
    if curso is None:
        erros.append("Seleccione o seu curso.")
    if password1 != password2:
        erros.append("As senhas não coincidem.")
    else:
        try:
            validate_password(password1, Usuario(email=email, nome=nome, sobrenome=sobrenome))
        except ValidationError as exc:
            erros.extend(exc.messages)
    if email and Usuario.objects.filter(email__iexact=email).exists():
        erros.append("Já existe uma conta com este e-mail.")

    if erros:
        for erro in erros:
            messages.error(request, erro)
        return redirect("cadastro")

    user = Usuario.objects.create_user(
        email=email,
        password=password1,
        nome=nome,
        sobrenome=sobrenome,
        telefone=telefone,
        perfil=perfil,
    )
    user.curso = curso
    user.depart = curso.departamento
    user.save()

    messages.success(request, "Conta criada com sucesso! Poderá entrar assim que a coordenação a activar.")
    return redirect("login")


@login_required
def atualizar_perfil(request):
    usuario = request.user

    if request.method == "POST":
        usuario.nome = request.POST.get("nome")
        usuario.sobrenome = request.POST.get("sobrenome")
        usuario.telefone = request.POST.get("telefone")

        if request.FILES.get("imagem"):
            usuario.imagem = request.FILES.get("imagem")

        senha_atual = request.POST.get("senha_atual")
        nova_senha = request.POST.get("nova_senha")
        confirmar_senha = request.POST.get("confirmar_senha")

        if senha_atual or nova_senha or confirmar_senha:
            if not check_password(senha_atual, usuario.password):
                messages.error(request, "Senha actual incorreta.")
                return redirect("atualizar_perfil")

            if nova_senha != confirmar_senha:
                messages.error(request, "As novas senhas não coincidem.")
                return redirect("atualizar_perfil")

            if len(nova_senha) < 8:
                messages.error(request, "A nova senha deve ter pelo menos 8 caracteres.")
                return redirect("atualizar_perfil")

            usuario.set_password(nova_senha)
            update_session_auth_hash(request, usuario)

        usuario.save()
        messages.success(request, "Perfil atualizado com sucesso.")
        return redirect("atualizar_perfil")

    return render(request, "Estudante/atualizar_perfil.html")
