"""Gestão de estudantes, professores e dossiês."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from ..models import Curso, Departamento, Usuario
from ..permissions import PERFIS_GESTAO, perfil_requerido


@perfil_requerido(*PERFIS_GESTAO)
def add_estudante(request):
    cursos = Curso.objects.select_related('departamento')
    tipos_usuario = Usuario.TIPOS_USUARIO

    if request.method == "POST":
        nome = request.POST.get("nome", "").strip()
        sobrenome = request.POST.get("sobrenome", "").strip()
        email = request.POST.get("email", "").strip()
        telefone = request.POST.get("telefone", "").strip()
        perfil = request.POST.get("perfil")
        curso_id = request.POST.get("curso")
        senha = request.POST.get("senha")
        confirmar = request.POST.get("confirmar_senha")

        if senha != confirmar:
            messages.error(request, "As senhas não coincidem.")
            return render(request, "admin/add_estudante.html", {"cursos": cursos, "TIPOS_USUARIO": tipos_usuario})

        if Usuario.objects.filter(email=email).exists():
            messages.error(request, "Este email já está registado.")
            return render(request, "admin/add_estudante.html", {"cursos": cursos, "TIPOS_USUARIO": tipos_usuario})

        curso = None
        departamento = None
        if curso_id:
            try:
                curso = Curso.objects.get(id=curso_id)
                departamento = curso.departamento
            except Curso.DoesNotExist:
                messages.error(request, "Curso inválido.")
                return render(request, "admin/add_estudante.html", {"cursos": cursos, "TIPOS_USUARIO": tipos_usuario})

        try:
            user = Usuario.objects.create_user(
                username=email,
                nome=nome,
                sobrenome=sobrenome,
                email=email,
                telefone=telefone,
                perfil=perfil,
                curso=curso,
                depart=departamento,
                estado_user="activo",
                password=senha
            )
            messages.success(request, f"{perfil.capitalize()} adicionado com sucesso!")
            return redirect("add_usuario")
        except Exception as e:
            messages.error(request, f"Erro ao criar utilizador: {e}")

    return render(request, "admin/add_estudante.html", {
        "cursos": cursos,
        "TIPOS_USUARIO": tipos_usuario,
        "titulo": "Adicionar Utilizador"
    })


@perfil_requerido(*PERFIS_GESTAO)
def alterar_estado_multiplos_usuarios(request):
    if request.method == "POST":
        ids = request.POST.getlist("usuarios")
        acao = request.POST.get("acao")
        if ids and acao in ["activar", "desativar"]:
            novo_estado = "activo" if acao == "activar" else "desativado"
            Usuario.objects.filter(id__in=ids).update(estado_user=novo_estado)

    return redirect("lista_estudantes")


@login_required
def lista_estudantes_tutor(request):
    if request.user.perfil != 'tutor':
        return redirect("login")
    estudantes_vinculados = (
        Usuario.objects.filter(perfil="estudante", temas__tutor_indicado=request.user)
        .select_related("curso")
        .prefetch_related("temas")
        .distinct()
        .order_by("nome", "sobrenome")
    )
    linhas = []
    for estudante in estudantes_vinculados:
        temas = [t for t in estudante.temas.all() if t.tutor_indicado_id == request.user.pk]
        tema = next((t for t in reversed(temas) if t.status_tutor == "aprovado"), temas[-1] if temas else None)
        documento = None
        if tema and tema.status_tutor == "aprovado":
            documento = tema.documentos_assinados.filter(anulado_em__isnull=True).first()
        linhas.append({"estudante": estudante, "tema": tema, "documento": documento})
    return render(request, "tutor/listas_estudantes.html", {"linhas": linhas})


@perfil_requerido(*PERFIS_GESTAO)
def gerenciar_professores(request):
    coordenador = request.user

    professores = Usuario.objects.filter(
        Q(perfil="presidente") & 
        (Q(curso=coordenador.curso) | Q(depart=coordenador.depart))
    ).order_by('-id')

    cursos = Curso.objects.filter(id=coordenador.curso_id) if coordenador.curso_id else Curso.objects.none()
    departamentos = Departamento.objects.filter(id=coordenador.depart_id) if coordenador.depart_id else Departamento.objects.none()
    
    if request.method == "POST":
        nome = request.POST.get('nome')
        sobrenome = request.POST.get('sobrenome')
        email = request.POST.get('email')
        telefone = request.POST.get('telefone')
        curso_id = request.POST.get('curso')
        depart_id = request.POST.get('depart')
        password = request.POST.get('password')
        
        if Usuario.objects.filter(email=email).exists():
            messages.error(request, "Já existe um usuário cadastrado com este e-mail.")
            return redirect('gerenciar_professores')
            
        try:
            final_curso_id = curso_id if curso_id and int(curso_id) == coordenador.curso_id else coordenador.curso_id
            final_depart_id = depart_id if depart_id and int(depart_id) == coordenador.depart_id else coordenador.depart_id

            professor = Usuario(
                nome=nome,
                sobrenome=sobrenome,
                email=email,
                telefone=telefone,
                perfil="presidente",
                estado_user="activo",
                curso_id=final_curso_id,
                depart_id=final_depart_id,
                is_staff=True
            )
            
            if password:
                professor.password = make_password(password)
            
            if 'imagem' in request.FILES:
                professor.imagem = request.FILES['imagem']
                
            professor.save()
            messages.success(request, f"Professor {nome} {sobrenome} cadastrado com sucesso!")
        except Exception as e:
            messages.error(request, f"Erro ao cadastrar: {str(e)}")
            
        return redirect('gerenciar_professores')

    context = {
        'professores': professores,
        'cursos': cursos,
        'departamentos': departamentos,
    }
    return render(request, 'admin/gerenciar_professores.html', context)


@perfil_requerido(*PERFIS_GESTAO)
@require_POST
def editar_professor(request, pk):
    coordenador = request.user
    
    professor = get_object_or_404(
        Usuario, 
        Q(pk=pk, perfil="presidente") & 
        (Q(curso=coordenador.curso) | Q(depart=coordenador.depart))
    )
    
    try:
        professor.nome = request.POST.get('nome')
        professor.sobrenome = request.POST.get('sobrenome')
        professor.email = request.POST.get('email')
        professor.telefone = request.POST.get('telefone')
        
        curso_id = request.POST.get('curso')
        depart_id = request.POST.get('depart')
        
        professor.curso_id = curso_id if curso_id else None
        professor.depart_id = depart_id if depart_id else None
        
        nova_senha = request.POST.get('password')
        if nova_senha and nova_senha.strip() != "":
            professor.password = make_password(nova_senha)
            
        if 'imagem' in request.FILES:
            professor.imagem = request.FILES['imagem']
            
        professor.save()
        messages.success(request, f"Dados do professor {professor.nome} atualizados!")
    except Exception as e:
        messages.error(request, f"Erro ao atualizar: {str(e)}")
        
    return redirect('gerenciar_professores')


@perfil_requerido(*PERFIS_GESTAO)
@require_POST
def alternar_status_professor(request, pk):
    coordenador = request.user
    
    professor = get_object_or_404(
        Usuario, 
        Q(pk=pk, perfil="presidente") & 
        (Q(curso=coordenador.curso) | Q(depart=coordenador.depart))
    )
    
    professor.estado_user = "desativado" if professor.estado_user == "activo" else "activo"
    professor.is_active = (professor.estado_user == "activo")
    professor.save()
    
    messages.success(request, f"Status do professor alterado para {professor.estado_user}.")
    return redirect('gerenciar_professores')


@perfil_requerido(*PERFIS_GESTAO)
@require_POST
def eliminar_professor(request, pk):
    coordenador = request.user
    
    professor = get_object_or_404(
        Usuario, 
        Q(pk=pk, perfil="presidente") & 
        (Q(curso=coordenador.curso) | Q(depart=coordenador.depart))
    )
    
    nome_completo = f"{professor.nome} {professor.sobrenome}"
    try:
        professor.delete()
        messages.success(request, f"Professor {nome_completo} removido do sistema.")
    except Exception as e:
        messages.error(request, f"Erro ao eliminar: {str(e)}")
        
    return redirect('gerenciar_professores')


@perfil_requerido(*PERFIS_GESTAO)
def perfil_documental(request, estudante_id):
    estudante = get_object_or_404(Usuario, pk=estudante_id, perfil='estudante')
    
    lista_de_documentos = estudante.obter_todos_documentos()
    
    return render(request, 'admin/perfil_documental.html', {
        'estudante': estudante,
        'documentos': lista_de_documentos
    })
