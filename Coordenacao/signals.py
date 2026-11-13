from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.urls import reverse  # Necessário para gerar as URLs
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
    if created:
        # Notificar Coordenador do curso
        coordenador = Usuario.objects.filter(perfil='cordenacao', curso=instance.estudante.curso).first()
        if coordenador:
            NotificacaoFinal.objects.create(
                usuario=coordenador, 
                titulo="Novo Tema Submetido", 
                mensagem=f"O estudante {instance.estudante.nome} submeteu o tema: '{instance.titulo}'.",
                link=reverse('lista_reprovados')
            )
        
        # Notificar Tutor indicado
        if instance.tutor_indicado:
            NotificacaoFinal.objects.create(
                usuario=instance.tutor_indicado, 
                titulo="Indicação de Orientação", 
                mensagem=f"Você foi indicado como orientador no tema: '{instance.titulo}'.",
                link=reverse('dashboard_tutor')
            )
    else:
        # Lógica para evitar notificação duplicada se o status não mudou
        # Usamos o 'raw' ou uma verificação simples no banco se necessário
        
        # Notificação de Status Final (Aprovado/Rejeitado)
        if instance.status_final in ['aprovado', 'rejeitado']:
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo=f"Tema {instance.status_final.capitalize()}",
                mensagem=f"O status final do seu tema '{instance.titulo}' foi definido como: {instance.get_status_final_display()}.",
                link=reverse('dashboard_estudante')
            )
        
        # Notificações intermediárias (Tutor ou Coordenação)
        # Exemplo: Se o tutor aprovou, avisa o estudante
        if instance.status_tutor != 'pendente':
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo="Atualização do Tutor",
                mensagem=f"O tutor atualizou o status do seu tema '{instance.titulo}' para: {instance.get_status_tutor_display()}.",
                link=reverse('dashboard_estudante')
            )

        # Exemplo: Se a coordenação aprovou, avisa o estudante
        if instance.status_coordenacao != 'pendente':
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo="Atualização da Coordenação",
                mensagem=f"A coordenação atualizou o status do seu tema '{instance.titulo}' para: {instance.get_status_coordenacao_display()}.",
                link=reverse('dashboard_estudante')
            )
@receiver(post_save, sender=Recomendacao)
def notificar_nova_recomendacao(sender, instance, created, **kwargs):
    if created:
        NotificacaoFinal.objects.create(
            usuario=instance.tema.estudante,
            titulo="Nova Recomendação",
            mensagem=f"O orientador {instance.tutor.nome} deixou correções no seu tema.",
            link=reverse('dashboard_estudante')
        )

# ==========================================
# 2. INSCRIÇÃO DE TFC
# ==========================================
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import InscricaoTFC, NotificacaoFinal, Usuario

@receiver(post_save, sender=InscricaoTFC)
def notificar_inscricao_tfc(sender, instance, created, **kwargs):
    # Evita processar durante operações em lote (bulk_create/update)
    if kwargs.get('raw', False):
        return

    # 1. Caso seja uma nova submissão do estudante
    if created:
        # Notifica a Coordenação/Área Científica do curso do estudante
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

    # 2. Caso seja uma atualização (Mudança de status ou Envio para Coordenação)
    else:
        # Recupera a instância anterior para comparar mudanças
        try:
            old_instance = InscricaoTFC.objects.get(pk=instance.pk)
        except InscricaoTFC.DoesNotExist:
            return

        # A: Notifica quando o coordenador marca como 'enviado_para_coordenacao'
        if not old_instance.enviado_para_coordenacao and instance.enviado_para_coordenacao:
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo="Ficha enviada para Coordenação",
                mensagem=f"Sua ficha TFC '{instance.tema.titulo}' foi enviada para análise da coordenação.",
                link=reverse('dashboard_estudante')
            )

        # B: Notifica o estudante quando a inscrição é APROVADA
        if old_instance.status != 'aprovado' and instance.status == 'aprovado':
            NotificacaoFinal.objects.create(
                usuario=instance.estudante,
                titulo="Inscrição de TFC Aprovada",
                mensagem="Parabéns! Sua inscrição de TFC foi validada e aprovada com sucesso.",
                link=reverse('dashboard_estudante')
            )

# ==========================================
# 3. PRÉ-DEFESAS & DESPACHOS
# ==========================================

@receiver(post_save, sender=Despacho)
def processar_assinatura_despacho(sender, instance, created, **kwargs):
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

# ==========================================
# 4. DEFESA PÚBLICA
# ==========================================

@receiver(post_save, sender=SolicitacaoDefesa)
def notificar_status_solicitacao_defesa(sender, instance, created, **kwargs):
    if not created and instance.status_solicitacao == 'autorizada':
        NotificacaoFinal.objects.create(
            usuario=instance.predefesa.estudante,
            titulo="Defesa Autorizada",
            mensagem=f"Sua defesa pública ocorrerá em {instance.data_defesa.strftime('%d/%m/%Y')}.",
            link=reverse('detalhes_solicitacao', kwargs={'pk': instance.pk})
        )

# ==========================================
# 5. COMUNICADOS
# ==========================================

@receiver(post_save, sender=Comunicado)
def disparar_comunicado_global(sender, instance, created, **kwargs):
    if instance.publicado and not created:
        estudantes = Usuario.objects.filter(estado_user='activo')
        for e in estudantes:
            NotificacaoFinal.objects.create(
                usuario=e,
                titulo="Comunicado Acadêmico",
                mensagem=f"Novo edital publicado: {instance.data_inicio} a {instance.data_fim}.",
                # Aponta para a rota que gera/baixa o PDF, passando o ID do comunicado
                link=reverse('baixar_comunicado_pdf', kwargs={'id': instance.id})
            )

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.urls import reverse
from .models import Predefesa, NotificacaoFinal

@receiver(post_save, sender=Predefesa)
def notificar_membros_banca_predefesa(sender, instance, created, **kwargs):
    if created:
        # Lista de todos os membros envolvidos
        membros_banca = [
            instance.presidente, 
            instance.primeiro_vogal, 
            instance.segundo_vogal, 
            instance.secretario
        ]
        
        # 1. Notificar o Estudante (com link para o PDF da banca)
        NotificacaoFinal.objects.create(
            usuario=instance.estudante,
            titulo="Agendamento de Pré-Defesa",
            mensagem=f"Sua pré-defesa foi agendada para o dia {instance.data.strftime('%d/%m/%Y')} às {instance.hora.strftime('%H:%M')}. Clique aqui para acessar o documento da banca.",
            link=reverse('pdf_predefesa', kwargs={'pk': instance.pk})
        )
        
        # 2. Notificar os membros da Banca (Presidente, Vogais e Secretário)
        for membro in membros_banca:
            if membro:  # Verifica se o campo não é nulo
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

    # 1. Quando o Despacho é CRIADO pela Área Científica
    if created:
        presidentes = Usuario.objects.filter(perfil='presidente')
        for p in presidentes:
            NotificacaoFinal.objects.create(
                usuario=p,
                titulo="Novo Despacho para Assinatura",
                mensagem=f"O despacho {instance.numero_despacho} está pronto para sua assinatura.",
                link=reverse('listar_despachos') # Redireciona para a lista onde ele pode ver o novo item
            )

    # 2. Quando o Despacho é APROVADO e vai para o Estudante/Área Científica
    else:
        # Usamos o método do Django para verificar mudanças nos campos se necessário
        # Aqui focamos no evento de aprovação final
        if instance.status == 'aprovado' and instance.publicado:
            
            # Notifica o Estudante (com link para baixar o PDF)
            NotificacaoFinal.objects.create(
                usuario=instance.predefesa.estudante,
                titulo="Despacho de Nomeação Aprovado",
                mensagem=f"Seu despacho {instance.numero_despacho} foi aprovado. Clique para baixar o PDF.",
                link=reverse('gerar_despacho_pdf', kwargs={'despacho_id': instance.id})
            )
            
            # Notifica a Área Científica (quem criou)
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

    # 1. Quando o Coordenador CRIA uma nova lista
    if created:
        # Notifica a Área Científica que uma nova lista de temas foi gerada
        responsaveis_cientifica = Usuario.objects.filter(perfil='area_cientifica')
        for admin in responsaveis_cientifica:
            NotificacaoFinal.objects.create(
                usuario=admin,
                titulo="Nova Lista de Temas Aprovados",
                mensagem=f"Uma nova lista ({instance.codigo_referencia}) foi submetida pelo coordenador.",
                link=reverse('area_cientifica_temas') 
            )

    # 2. Quando o Status da lista muda (Ex: Enviado para Área Científica)
    else:
        # Precisamos verificar se o status foi alterado para 'enviado'
        # Nota: Como o seu modelo tem um método .enviar_para_area_cientifica(), 
        # o sinal disparará assim que o status mudar no banco.
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

    # Filtra usuários da Área Científica
    responsaveis_cientifica = Usuario.objects.filter(perfil='area_cientifica')

    # 1. Quando uma nova Lista de Pré-defesas é criada pela Coordenação
    if created:
        for admin in responsaveis_cientifica:
            NotificacaoFinal.objects.create(
                usuario=admin,
                titulo="Nova Remessa de Pré-defesas",
                mensagem=f"A coordenação gerou uma nova remessa (Ref: {instance.id}).",
                link=reverse('lista_cursos_predefesas')
            )

    # 2. Quando a Coordenação muda o status para 'enviado'
    else:
        # Acessa o estado anterior para garantir que a notificação ocorra apenas na mudança
        # Nota: Usamos o ID para buscar a versão salva anteriormente
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
    # Verifica se a instância foi criada e se está ativa
    if created and instance.ativo:
        
        # O filtro abaixo busca todos os estudantes do curso relacionado ao calendário
        estudantes = Usuario.objects.filter(
            perfil='estudante',
            curso=instance.curso
        )

        # Opcional: Se você quiser filtrar também pelo período, 
        # a lógica deve buscar o período dentro do modelo CalendarioAprovacao 
        # mas a filtragem no Usuario deve ser feita conforme os campos existentes dele.

        for estudante in estudantes:
            NotificacaoFinal.objects.create(
                usuario=estudante,
                titulo="Nova Data de Aprovação de Temas",
                mensagem=f"Foi definida uma nova data de aprovação para o dia {instance.data_aprovacao.strftime('%d/%m/%Y às %H:%M')}. Prepare-se!",
                link="/estudante/" 
            )