from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.urls import reverse
from .models import (
    Usuario, Tema, Recomendacao, Predefesa, Despacho, 
    SolicitacaoDefesa, ActaDefesa, ListaTemasAprovados, 
    InscricaoTFC, NotificacaoFinal, Comunicado
)

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import Tema, NotificacaoFinal, Usuario

@receiver(post_save, sender=Tema)
def notificar_mudanca_status_tema(sender, instance, created, **kwargs):
    # no loaddata não queremos notificações duplicadas
    if kwargs.get('raw', False):
        return
    if created:
        coordenador = Usuario.objects.filter(perfil='cordenacao', curso=instance.estudante.curso).first()
        if coordenador:
            NotificacaoFinal.objects.create(
                usuario=coordenador, 
                titulo="Novo Tema Submetido", 
                mensagem=f"O estudante {instance.estudante.nome} submeteu o tema: '{instance.titulo}'.",
                link=reverse('lista_reprovados')
            )
        
        if instance.tutor_indicado:
            NotificacaoFinal.objects.create(
                usuario=instance.tutor_indicado, 
                titulo="Indicação de Orientação", 
                mensagem=f"Você foi indicado como orientador no tema: '{instance.titulo}'.",
                link=reverse('dashboard_tutor')
            )
    else:
        
        if instance.status_final in ['aprovado', 'rejeitado']:
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo=f"Tema {instance.status_final.capitalize()}",
                mensagem=f"O status final do seu tema '{instance.titulo}' foi definido como: {instance.get_status_final_display()}.",
                link=reverse('dashboard_estudante')
            )
        
        if instance.status_tutor != 'pendente':
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo="Atualização do Tutor",
                mensagem=f"O tutor atualizou o status do seu tema '{instance.titulo}' para: {instance.get_status_tutor_display()}.",
                link=reverse('dashboard_estudante')
            )

        if instance.status_coordenacao != 'pendente':
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo="Atualização da Coordenação",
                mensagem=f"A coordenação atualizou o status do seu tema '{instance.titulo}' para: {instance.get_status_coordenacao_display()}.",
                link=reverse('dashboard_estudante')
            )
@receiver(post_save, sender=Recomendacao)
def notificar_nova_recomendacao(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    # as da banca são avisadas de uma vez, quando a sessão de pré-defesa é encerrada
    if created and not instance.predefesa_id:
        nome = instance.tutor.nome if instance.tutor else "O seu orientador"
        NotificacaoFinal.objects.create(
            usuario=instance.tema.estudante,
            titulo="Nova Recomendação",
            mensagem=f"{nome} deixou uma recomendação no seu tema.",
            link=reverse('todas_recomendacoes')
        )

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import InscricaoTFC, NotificacaoFinal, Usuario

@receiver(post_save, sender=InscricaoTFC)
def notificar_inscricao_tfc(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return

    if created:
        responsaveis = Usuario.objects.filter(
            perfil__in=['area_cientifica'], 
            curso=instance.estudante.curso
        )
        for admin in responsaveis:
            NotificacaoFinal.objects.create(
                usuario=admin,
                titulo="Nova Submissão de TFC",
                mensagem=f"O estudante {instance.estudante.nome} submeteu uma nova ficha de inscrição TFC.",
                link=reverse('lista_inscricoes_pendentes')
            )

    else:
        try:
            old_instance = InscricaoTFC.objects.get(pk=instance.pk)
        except InscricaoTFC.DoesNotExist:
            return

        if not old_instance.enviado_para_coordenacao and instance.enviado_para_coordenacao:
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo="Ficha enviada para Coordenação",
                mensagem=f"Sua ficha TFC '{instance.tema.titulo}' foi enviada para análise da coordenação.",
                link=reverse('dashboard_estudante')
            )

        if old_instance.status != 'aprovado' and instance.status == 'aprovado':
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo="Inscrição de TFC Aprovada",
                mensagem="Parabéns! Sua inscrição de TFC foi validada e aprovada com sucesso.",
                link=reverse('dashboard_estudante')
            )


@receiver(post_save, sender=Despacho)
def processar_assinatura_despacho(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    if not created and instance.status == 'aprovado' and instance.publicado:
        banca = [instance.predefesa.estudante, instance.predefesa.presidente, instance.predefesa.primeiro_vogal, instance.predefesa.segundo_vogal]
        for user in banca:
            if user:
                NotificacaoFinal.objects.create(
                    usuario=user,
                    titulo="Despacho de Júri",
                    mensagem=f"O Despacho nº {instance.numero_despacho} foi publicado oficialmente.",
                    link=reverse('listar_despachos')
                )


@receiver(post_save, sender=SolicitacaoDefesa)
def notificar_status_solicitacao_defesa(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    if not created and instance.status_solicitacao == 'autorizada':
        NotificacaoFinal.objects.create(
            usuario=instance.predefesa.estudante,
            titulo="Defesa Autorizada",
            mensagem=f"Sua defesa pública ocorrerá em {instance.data_defesa.strftime('%d/%m/%Y')}.",
            link=reverse('detalhes_solicitacao', kwargs={'pk': instance.pk})
        )


@receiver(post_save, sender=Comunicado)
def disparar_comunicado_global(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    if instance.publicado and not created:
        estudantes = Usuario.objects.filter(estado_user='activo')
        for e in estudantes:
            NotificacaoFinal.objects.create(
                usuario=e,
                titulo="Comunicado Acadêmico",
                mensagem=f"Novo edital publicado: {instance.data_inicio} a {instance.data_fim}.",
                link=reverse('baixar_comunicado_pdf', kwargs={'id': instance.id})
            )

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import Predefesa, NotificacaoFinal

@receiver(post_save, sender=Predefesa)
def notificar_membros_banca_predefesa(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    if created:
        membros_banca = [
            instance.presidente, 
            instance.primeiro_vogal, 
            instance.segundo_vogal, 
            instance.secretario
        ]
        
        NotificacaoFinal.objects.create(
            usuario=instance.estudante,
            titulo="Agendamento de Pré-Defesa",
            mensagem=f"Sua pré-defesa foi agendada para o dia {instance.data.strftime('%d/%m/%Y')} às {instance.hora.strftime('%H:%M')}. Clique aqui para acessar o documento da banca.",
            link=reverse('pdf_predefesa', kwargs={'pk': instance.pk})
        )
        
        for membro in membros_banca:
            if membro:
                NotificacaoFinal.objects.create(
                    usuario=membro,
                    titulo="Nova Banca de Pré-Defesa",
                    mensagem=f"Você foi designado para a banca do estudante {instance.estudante.nome}. Data: {instance.data.strftime('%d/%m/%Y')} às {instance.hora.strftime('%H:%M')}. Documento oficial disponível.",
                    link=reverse('pdf_predefesa', kwargs={'pk': instance.pk})
                )

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import Despacho, NotificacaoFinal, Usuario

@receiver(post_save, sender=Despacho)
def notificar_fluxo_despacho(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return

    if created:
        presidentes = Usuario.objects.filter(perfil='presidente')
        for p in presidentes:
            NotificacaoFinal.objects.create(
                usuario=p,
                titulo="Novo Despacho para Assinatura",
                mensagem=f"O despacho {instance.numero_despacho} está pronto para sua assinatura.",
                link=reverse('listar_despachos')
            )

    else:
        if instance.status == 'aprovado' and instance.publicado:
            
            NotificacaoFinal.objects.create(
                usuario=instance.predefesa.estudante,
                titulo="Despacho de Nomeação Aprovado",
                mensagem=f"Seu despacho {instance.numero_despacho} foi aprovado. Clique para baixar o PDF.",
                link=reverse('gerar_despacho_pdf', kwargs={'despacho_id': instance.id})
            )
            
            if instance.criado_por:
                NotificacaoFinal.objects.create(
                    usuario=instance.criado_por,
                    titulo="Despacho Assinado",
                    mensagem=f"O despacho {instance.numero_despacho} foi assinado e está disponível.",
                    link=reverse('gerar_despacho_pdf', kwargs={'despacho_id': instance.id})
                )
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import ListaTemasAprovados, NotificacaoFinal, Usuario

@receiver(post_save, sender=ListaTemasAprovados)
def notificar_fluxo_lista_temas(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return

    if created:
        responsaveis_cientifica = Usuario.objects.filter(perfil='area_cientifica')
        for admin in responsaveis_cientifica:
            NotificacaoFinal.objects.create(
                usuario=admin,
                titulo="Nova Lista de Temas Aprovados",
                mensagem=f"Uma nova lista ({instance.codigo_referencia}) foi submetida pelo coordenador.",
                link=reverse('area_cientifica_temas') 
            )

    else:
        if instance.status == 'enviado':
            responsaveis_cientifica = Usuario.objects.filter(perfil='area_cientifica')
            for admin in responsaveis_cientifica:
                NotificacaoFinal.objects.create(
                    usuario=admin,
                    titulo="Lista de Temas Enviada",
                    mensagem=f"A lista {instance.codigo_referencia} foi enviada para processamento.",
                    link=reverse('area_cientifica_temas')
                )
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import ListaPreDefesas, NotificacaoFinal, Usuario

@receiver(post_save, sender=ListaPreDefesas)
def notificar_remessa_predefesas(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return

    responsaveis_cientifica = Usuario.objects.filter(perfil='area_cientifica')

    if created:
        for admin in responsaveis_cientifica:
            NotificacaoFinal.objects.create(
                usuario=admin,
                titulo="Nova Remessa de Pré-defesas",
                mensagem=f"A coordenação gerou uma nova remessa (Ref: {instance.id}).",
                link=reverse('lista_cursos_predefesas')
            )

    else:
        old_instance = ListaPreDefesas.objects.get(pk=instance.pk)
        
        if old_instance.status != 'enviado' and instance.status == 'enviado':
            for admin in responsaveis_cientifica:
                NotificacaoFinal.objects.create(
                    usuario=admin,
                    titulo="Remessa Enviada para Processamento",
                    mensagem=f"A remessa ID {instance.id} foi enviada pela coordenação.",
                    link=reverse('lista_cursos_predefesas')
                )
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import CalendarioAprovacao, NotificacaoFinal, Usuario

@receiver(post_save, sender=CalendarioAprovacao)
def notificar_estudantes_data_aprovacao(sender, instance, created, **kwargs):
    if kwargs.get('raw', False):
        return
    if created and instance.ativo:
        
        estudantes = Usuario.objects.filter(
            perfil='estudante',
            curso=instance.curso
        )

        for estudante in estudantes:
            NotificacaoFinal.objects.create(
                usuario=estudante,
                titulo="Nova Data de Aprovação de Temas",
                mensagem=f"Foi definida uma nova data de aprovação para o dia {instance.data_aprovacao.strftime('%d/%m/%Y às %H:%M')}. Prepare-se!",
                link="/estudante/" 
            )
