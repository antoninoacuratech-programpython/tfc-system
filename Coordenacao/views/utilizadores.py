"""Gestão de estudantes, professores e dossiês."""

import io
import os
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.hashers import make_password
from django.contrib.staticfiles import finders
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import HRFlowable, Image, Paragraph, SimpleDocTemplate, Spacer, Table

from ..models import Curso, Departamento, Tema, Usuario
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
def gerar_pdf_declaracao_orientador(request, usuario_id):
    try:
        estudante = get_object_or_404(Usuario, pk=usuario_id, perfil='estudante')
        
        tema = Tema.objects.filter(estudante=estudante, status_tutor='aprovado').last()
        
        if not tema:
            messages.error(request, "Não foi encontrado um tema aprovado para este estudante.")
            return redirect('lista_estudantes_tutor')

        orientador = tema.tutor_indicado
        nome_curso = str(estudante.curso.nome).upper() if estudante.curso else "ENGENHARIA INFORMÁTICA"
        
        nome_depto = "ENGENHARIAS"
        if hasattr(estudante, 'departamento') and estudante.departamento:
            nome_depto = str(estudante.departamento.nome).upper()
        elif hasattr(estudante, 'depart') and estudante.depart:
            nome_depto = str(estudante.depart.nome).upper()

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer, 
            pagesize=A4, 
            rightMargin=50, leftMargin=50, topMargin=40, bottomMargin=60
        )
        elements = []

        style_inst_bold = ParagraphStyle('InstBold', fontSize=10, fontName='Helvetica-Bold', leading=12, alignment=TA_CENTER)
        style_dept = ParagraphStyle('Dept', fontSize=9, fontName='Helvetica-Bold', leading=11, alignment=TA_CENTER, textColor=colors.gray)
        style_titulo = ParagraphStyle('Titulo', fontSize=12, fontName='Helvetica-Bold', alignment=TA_CENTER, spaceBefore=20, spaceAfter=20)
        style_corpo = ParagraphStyle('Corpo', fontSize=11, fontName='Helvetica', leading=16, alignment=TA_JUSTIFY)

        relative_path = 'imgs/icons/finalispbie.jpg'
        logo_path = finders.find(relative_path)
        
        if logo_path and os.path.exists(logo_path):
            try:
                logo_img = Image(logo_path, width=2.2*cm, height=2.2*cm)
            except:
                logo_img = Paragraph("<b>ISPB</b>", style_inst_bold)
        else:
            logo_img = Paragraph("<b>ISPB</b>", style_inst_bold)

        header_info = [
            Paragraph("REPÚBLICA DE ANGOLA", style_inst_bold),
            Paragraph("MINISTÉRIO DO ENSINO SUPERIOR, CIÊNCIA, TECNOLOGIA E INOVAÇÃO", style_inst_bold),
            Paragraph("INSTITUTO SUPERIOR POLITÉCNICO DO BIÉ", style_inst_bold),
            Paragraph(f"DEPARTAMENTO DE {nome_depto}", style_dept),
            Paragraph(f"CURSO DE {nome_curso}", style_dept),
        ]

        elements.append(Table([[logo_img, header_info]], colWidths=[2.5*cm, 13.5*cm]))
        elements.append(Spacer(1, 5))
        elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
        
        elements.append(Paragraph("DECLARAÇÃO DE RESPONSABILIDADE DO (A) ORIENTADOR (A)", style_titulo))

        nome_est_comp = f"{estudante.nome} {estudante.sobrenome}".upper()
        nome_ori_comp = f"{orientador.nome} {orientador.sobrenome}" if orientador else "_____________________"
        
        texto = f"""
        Para os devidos efeitos, eu, docente do Departamento de {nome_depto.capitalize()}, 
        orientador (a) do trabalho de Fim de Curso do (a) estudante <b>{nome_est_comp}</b>, 
        do Instituto Superior Politécnico do Bié, com o tema: <u>{tema.titulo}</u>.
        <br/><br/>
        Por este meio confirmar que o trabalho em referência se encontra concluído e que o estudante 
        está preparado para assumir a sua defesa pública.
        """
        elements.append(Paragraph(texto, style_corpo))
        elements.append(Spacer(1, 20))

        hoje = date.today()
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho", "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        data_str = f"Cuito, aos {hoje.day} de {meses[hoje.month-1]} de {hoje.year}"
        elements.append(Paragraph(data_str, ParagraphStyle('Date', alignment=TA_RIGHT, fontSize=11)))
        
        elements.append(Spacer(1, 40))
        assinaturas = [
            [Paragraph("VISTO<br/>______/_________/20___", style_corpo), ""],
            [Spacer(1, 30), Spacer(1, 30)],
            [Paragraph("O Vice-Presidente P/Assuntos Científicos", style_corpo), Paragraph("O orientador (a)", style_corpo)],
            [Paragraph("_____________________________________", style_inst_bold), Paragraph("_____________________________________", style_inst_bold)],
            ["", Paragraph(nome_ori_comp, style_inst_bold)]
        ]
        elements.append(Table(assinaturas, colWidths=[8*cm, 8*cm]))

        elements.append(Spacer(1, 40))
        rodape = Paragraph("Rua Padre Fidalgo entre Artur de Paiva e Francisco de Leite Cardoso S/N, Cidade do Cuito-Bié", 
                           ParagraphStyle('R', fontSize=7, alignment=TA_CENTER, textColor=colors.grey))
        elements.append(rodape)

        doc.build(elements)
        buffer.seek(0)
        return HttpResponse(buffer, content_type='application/pdf')

    except Exception as e:
        print(f"ERRO: {e}")
        return HttpResponse(f"Erro ao gerar PDF: {str(e)}", status=500)


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
    return render(request, "tutor/listas_estudantes.html", {
        "estudantes": estudantes_vinculados
    })


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
