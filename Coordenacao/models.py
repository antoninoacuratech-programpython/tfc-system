from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import os




class Departamento(models.Model):
    nome = models.CharField(max_length=150, unique=True)
    descricao = models.TextField(max_length=800)

    def __str__(self):
        return self.nome


class Curso(models.Model):
    nome = models.CharField(max_length=200)
    descricao = models.CharField(max_length=500)

    departamento = models.ForeignKey(
    Departamento,
    on_delete=models.PROTECT,
    related_name='cursos'
)



    def __str__(self):
        return f"{self.nome} - {self.departamento.nome}"




class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("O campo Email é obrigatório")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)


from django.db import models
from django.contrib.auth.models import AbstractUser

class Usuario(AbstractUser):
    TIPOS_USUARIO = (
        ("cordenacao", "cordenacao"),
        ("dac", "dac"),
        ("presidente", "professores"),
        ("estudante", "estudante"),
        ("area_cientifica", "area_cientifica"),
        ("tutor", "tutor"),
        ("area_etica", "area_etica"),
    )

    ESTADO_USUARIO = (
        ("activo", "activo"),
        ("desativado", "desativado"),
    )

    username = None
    email = models.EmailField(unique=True)
    nome = models.CharField(max_length=100)
    sobrenome = models.CharField(max_length=100)
    imagem = models.ImageField(
        upload_to="usuarios/",
        null=True,
        blank=True
    )

    perfil = models.CharField(
        max_length=20,
        choices=TIPOS_USUARIO,
    )

    estado_user = models.CharField(
        max_length=20,
        choices=ESTADO_USUARIO,
        default="desativado"
    )
    curso = models.ForeignKey(
        Curso, on_delete=models.SET_NULL, null=True, blank=True
    )
    depart = models.ForeignKey(
        Departamento, on_delete=models.SET_NULL, null=True, blank=True
    )
    telefone = models.CharField(max_length=9)
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["nome", "sobrenome"]

    objects = UsuarioManager()
    # Dentro da sua classe Usuario(AbstractUser) em models.py

    def obter_todos_documentos(self):
        """
        Retorna uma lista consolidada de todos os ficheiros (FileField/ImageField)
        do estudante, percorrendo todo o ciclo de vida do TFC.
        """
        docs = []

        # 1. Inscrições TFC
        for i in self.inscricoes_tfc.all():
            if i.requerimento: docs.append({'nome': 'Inscrição: Requerimento', 'url': i.requerimento.url})
            if i.curriculum_academico: docs.append({'nome': 'Inscrição: Currículo', 'url': i.curriculum_academico.url})
            if i.copia_bi: docs.append({'nome': 'Inscrição: Cópia BI', 'url': i.copia_bi.url})

        # 2. Temas
        for t in self.temas.all():
            if t.resumo: docs.append({'nome': 'Tema: Resumo', 'url': t.resumo.url})
            if t.requerimento: docs.append({'nome': 'Tema: Requerimento', 'url': t.requerimento.url})

        # 3. Pré-defesas e fluxos vinculados (Solicitações/Actas)
        for pd in self.minhas_predefesas.all():
            if hasattr(pd, 'solicitacao_defesa'):
                docs.append({'nome': 'Solicitação de Defesa', 'url': '#'}) # Ajuste para o campo real do PDF
                
                # Se houver acta final vinculada
                if hasattr(pd.solicitacao_defesa, 'acta_final'):
                    docs.append({'nome': f'Acta de Defesa: {pd.solicitacao_defesa.acta_final.numero_acta}', 'url': '#'})

        return docs

    def __str__(self):
        return f"{self.nome} {self.sobrenome} ({self.perfil})"

        

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
class ProcessoEtapa(models.Model):
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name='processos')
    coordenador = models.ForeignKey(Usuario, on_delete=models.PROTECT, limit_choices_to={'perfil': 'cordenacao'})
    
    titulo = models.CharField(max_length=100, help_text="Ex: Processo TFC 2026.1")
    data_inicio = models.DateField()
    data_termino = models.DateField()
    
    ativo = models.BooleanField(default=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Abertura de Processo"
        verbose_name_plural = "Abertura de Processos"

    def __str__(self):
        return f"{self.titulo} - {self.curso.nome} ({self.data_inicio} a {self.data_termino})"

    def is_periodo_valido(self):
        hoje = timezone.now().date()
        return self.data_inicio <= hoje <= self.data_termino and self.ativo

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class Tema(models.Model):
    STATUS_TUTOR = (
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado pelo tutor'),
        ('rejeitado', 'Rejeitado pelo tutor'),
    )

    STATUS_COORD = (
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado pela coordenação'),
        ('rejeitado', 'Rejeitado pela coordenação'),
    )

    STATUS_FINAL = (
        ('pendente', 'Pendente'),
        ('aprovado', 'Aprovado'),
        ('rejeitado', 'Rejeitado'),
    )

    # Relacionamentos Principais
    estudante = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        related_name='temas',
        limit_choices_to={'perfil': 'estudante'}
    )
    
    # Campo preenchido automaticamente no clean/save
    processo = models.ForeignKey(
        'ProcessoEtapa',
        on_delete=models.CASCADE,
        related_name='temas_vinculados',
        verbose_name="Processo de Origem",
        help_text="Processo ativo no momento da submissão",
        null=True,
        blank=True
    )

    # Dados do Tema
    titulo = models.CharField(max_length=200)
    descricao = models.TextField()
    resumo = models.FileField(upload_to='resumos/', blank=True, null=True)
    requerimento = models.FileField(upload_to='requer/', blank=True, null=True)

    tutor_indicado = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='temas_orientados',
        limit_choices_to={'perfil': 'tutor'}
    )

    # Fluxo de Status
    status_tutor = models.CharField(max_length=15, choices=STATUS_TUTOR, default='pendente')
    status_coordenacao = models.CharField(max_length=20, choices=STATUS_COORD, default='pendente')
    status_final = models.CharField(max_length=15, choices=STATUS_FINAL, default='pendente')

    # Metadados
    data_envio = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tema"
        verbose_name_plural = "Temas"
        ordering = ['-data_envio']

    def clean(self):
        """
        Valida a existência de um processo aberto e o vincula ao tema.
        """
        super().clean()
        
        if self.estudante and hasattr(self.estudante, 'curso') and self.estudante.curso:
            hoje = timezone.now().date()
            
            # Busca o processo ativo para o curso do aluno
            processo_ativo = ProcessoEtapa.objects.filter(
                curso=self.estudante.curso,
                ativo=True,
                data_inicio__lte=hoje,
                data_termino__gte=hoje
            ).first()

            if not processo_ativo:
                raise ValidationError(
                    f"Não há um processo de submissão aberto para o curso "
                    f"{self.estudante.curso.nome} nesta data ({hoje.strftime('%d/%m/%Y')})."
                )
            
            # Vincula o tema ao processo encontrado
            self.processo = processo_ativo
        else:
            raise ValidationError("O estudante precisa estar vinculado a um curso para criar um tema.")

    def save(self, *args, **kwargs):
        # 1. Garante a validação de processo apenas na criação (ou se for necessário revalidar)
        if not self.pk:
            self.full_clean()

        # 2. Lógica de consolidação do Status Final
        if self.status_tutor == 'aprovado' and self.status_coordenacao == 'aprovado':
            self.status_final = 'aprovado'
        elif self.status_tutor == 'rejeitado' or self.status_coordenacao == 'rejeitado':
            self.status_final = 'rejeitado'
        else:
            self.status_final = 'pendente'

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.titulo} - {self.estudante.nome}"

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class Recomendacao(models.Model):
    tema = models.ForeignKey(
        'Tema',
        on_delete=models.CASCADE,
        related_name='recomendacoes'
    )
    tutor = models.ForeignKey(
        'Usuario',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        limit_choices_to={'perfil': 'tutor'},
        related_name='recomendacoes_feitas'
    )
    texto = models.TextField()
    lida = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-data_criacao']
        verbose_name = "Recomendação"
        verbose_name_plural = "Recomendações"

    def clean(self):
        """
        Garante que recomendações só sejam feitas se o processo do curso 
        do tema estiver dentro do período de vigência.
        """
        super().clean()
        
        # O curso do processo é extraído através do estudante dono do tema
        if self.tema and self.tema.estudante and self.tema.estudante.curso:
            hoje = timezone.now().date()
            curso_do_tema = self.tema.estudante.curso
            
            processo = ProcessoEtapa.objects.filter(
                curso=curso_do_tema,
                ativo=True,
                data_inicio__lte=hoje,
                data_termino__gte=hoje
            ).first()

            if not processo:
                raise ValidationError(
                    f"Não é possível enviar recomendações. O processo para o curso "
                    f"{curso_do_tema.nome} está encerrado ou não foi aberto."
                )

    def save(self, *args, **kwargs):
        # Força a validação do período antes de salvar
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        tutor_nome = self.tutor if self.tutor else "Tutor Removido"
        return f"Recomendação de {tutor_nome} para '{self.tema.titulo}'"
from datetime import datetime, timedelta
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class Predefesa(models.Model):
    data = models.DateField()
    hora = models.TimeField()
    
    estudante = models.ForeignKey(
        'Usuario', 
        on_delete=models.CASCADE, 
        limit_choices_to={'perfil': 'estudante'},
        related_name='minhas_predefesas'
    )
    
    tema = models.ForeignKey(
        'Tema', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True
    )

    secretario = models.ForeignKey(
        'Usuario', 
        on_delete=models.SET_NULL, 
        null=True,
        limit_choices_to={'perfil': 'tutor'},
        related_name='atuacoes_secretario'
    )

    # Definição dos três Júris específicos
    presidente = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE, 
        limit_choices_to={'perfil': 'tutor'}, related_name='presidencias'
    )
    primeiro_vogal = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE, 
        limit_choices_to={'perfil': 'tutor'}, related_name='vogal1_atuacoes'
    )
    segundo_vogal = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE, 
        limit_choices_to={'perfil': 'tutor'}, related_name='vogal2_atuacoes'
    )

    def clean(self):
        super().clean()
        if not self.estudante:
            return

        # --- 1. VALIDAÇÃO DO PROCESSO ABERTO PELO COORDENADOR ---
        if self.estudante.curso:
            hoje = timezone.now().date()
            processo = ProcessoEtapa.objects.filter(
                curso=self.estudante.curso,
                ativo=True,
                data_inicio__lte=hoje,
                data_termino__gte=hoje
            ).first()

            if not processo:
                raise ValidationError(
                    f"Não é possível agendar pré-defesas. O processo para o curso de "
                    f"{self.estudante.curso.nome} não está aberto ou já expirou."
                )
        
        # --- 2. VALIDAÇÃO DO TEMA E ORIENTADOR ---
        tema_obj = Tema.objects.filter(estudante=self.estudante).order_by('-data_envio').first()
        if not tema_obj:
            raise ValidationError(f"O estudante {self.estudante} não possui um tema registrado.")
        
        self.tema = tema_obj
        tutor_do_estudante = tema_obj.tutor_indicado
        
        juris_selecionados = [self.presidente, self.primeiro_vogal, self.segundo_vogal, self.secretario]

        # Cada docente só pode ocupar uma função na mesma mesa de júri.
        ids_juri = [j.pk for j in juris_selecionados if j is not None]
        if len(ids_juri) != len(set(ids_juri)):
            raise ValidationError(
                "O mesmo docente não pode ocupar mais de uma função na mesa de júri "
                "(presidente, secretário, 1º vogal e 2º vogal devem ser pessoas diferentes)."
            )

        for juri in juris_selecionados:
            if juri == tutor_do_estudante:
                raise ValidationError(f"Conflito: O orientador {juri} não pode fazer parte da Mesa de Júri deste estudante.")
        
        # --- 3. VERIFICAÇÃO DE HORÁRIO (Intervalo de 1h30) ---
        self.validar_conflito_horario(juris_selecionados)

    def validar_conflito_horario(self, juris):
        dt_atual = datetime.combine(self.data, self.hora)
        margem = timedelta(hours=1, minutes=30)
        
        predefesas_dia = Predefesa.objects.filter(data=self.data).exclude(id=self.id)
        
        for p in predefesas_dia:
            dt_existente = datetime.combine(p.data, p.hora)
            if abs(dt_atual - dt_existente) < margem:
                juris_ocupados = [p.presidente, p.primeiro_vogal, p.segundo_vogal, p.secretario]
                for j in juris:
                    if j in juris_ocupados and j is not None:
                        raise ValidationError(
                            f"O professor {j.nome} {j.sobrenome} já tem uma pré-defesa às {p.hora}. "
                            f"Deve haver um intervalo de pelo menos 1h30."
                        )

    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Banca de {self.estudante.nome} - {self.data} às {self.hora}"

from django.db import models
from django.conf import settings
from django.utils import timezone



class Comunicado(models.Model):
    data_inicio = models.DateField()
    data_fim = models.DateField()

    hora_inicio = models.TimeField()
    hora_fim = models.TimeField()

    taxa_finalistas_antigos = models.DecimalField(
        max_digits=10, decimal_places=2, default=10000
    )
    taxa_pos_laboral_tfc = models.DecimalField(
        max_digits=10, decimal_places=2, default=75000
    )
    taxa_pos_laboral_exame = models.DecimalField(
        max_digits=10, decimal_places=2, default=30000
    )

    publicado = models.BooleanField(default=False)
    data_publicacao = models.DateTimeField(null=True, blank=True)

    criado_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Comunicado ({self.data_inicio} - {self.data_fim})"


class Notificacao(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="notificacoes")
    comunicado = models.ForeignKey(Comunicado, on_delete=models.CASCADE)
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notificação - {self.usuario}"
from django.db import models



def current_year():
    return timezone.now().year

class InscricaoTFC(models.Model):
    PERIODO_CHOICES = [
        ('Regular', 'Regular'),
        ('Pós-Laboral', 'Pós-Laboral'),
    ]

    STATUS_CHOICES = [
        ('pendente', 'Pendente'),
        ('aprovado', 'Inscrição feita com sucesso'),
    ]

    # Relacionamentos
    estudante = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='inscricoes_tfc')
    tema = models.OneToOneField('Tema', on_delete=models.CASCADE, related_name='ficha_inscricao')
    # Adicione este campo dentro da sua class InscricaoTFC(models.Model):
    enviado_para_coordenacao = models.BooleanField(default=False)
    # Informações Académicas e Pessoais
    periodo = models.CharField(max_length=20, choices=PERIODO_CHOICES, default='Regular')
    nacionalidade = models.CharField(max_length=50, default="Angolana")
    endereco = models.CharField(max_length=255)
    local_desenvolvimento = models.CharField(max_length=255)
    ano_conclusao_curriculo = models.PositiveIntegerField(default=current_year)
    
    # --- NOVOS CAMPOS DE FICHEIROS ADICIONADOS ---
    requerimento = models.FileField(upload_to='tfc/requerimentos/', null=True, blank=True)
    curriculum_academico = models.FileField(upload_to='tfc/curriculos/', null=True, blank=True)
    ficha_reconfirmacao = models.FileField(upload_to='tfc/fichas/', null=True, blank=True)
    comprovativo_pagamento = models.FileField(upload_to='tfc/pagamentos/', null=True, blank=True)
    copia_bi = models.FileField(upload_to='tfc/documentos_id/', null=True, blank=True)
    # ---------------------------------------------

    # Status e Auditoria
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pendente')
    aprovado_por = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='validador_tfc'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    def clean(self):
        """
        Verifica se existe um processo aberto pelo coordenador para o curso 
        do estudante antes de permitir a inscrição.
        """
        super().clean()
        
        if self.estudante and self.estudante.curso:
            hoje = timezone.now().date()
            
            # Busca o processo ativo para o curso do estudante
            from .models import ProcessoEtapa # Import local para evitar circularidade se necessário
            processo = ProcessoEtapa.objects.filter(
                curso=self.estudante.curso,
                ativo=True,
                data_inicio__lte=hoje,
                data_termino__gte=hoje
            ).first()

            if not processo:
                raise ValidationError(
                    f"Inscrição bloqueada: O período de inscrições para o curso de "
                    f"{self.estudante.curso.nome} não está aberto no momento."
                )
        else:
            raise ValidationError("O estudante precisa estar vinculado a um curso para realizar a inscrição.")

    def save(self, *args, **kwargs):
        # Força a execução do clean() para garantir a validação de data
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ficha {self.id} - {self.estudante.nome}"

class NotificacaoTFC(models.Model):
    # Quem enviou (Ex: O coordenador que aprovou)
    remetente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificacoes_enviadas')
    
    # O destinatário específico (Ex: O estudante dono da ficha)
    # Colocamos null=True e blank=True para caso queira enviar uma notificação geral para a área científica sem um usuário específico
    destinatario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificacoes_recebidas', null=True, blank=True)
    
    # Define o grupo alvo: 'area_cientifica' ou 'estudante'
    destinatario_perfil = models.CharField(max_length=20, default='area_cientifica') 
    
    mensagem = models.TextField()
    inscricao = models.ForeignKey('InscricaoTFC', on_delete=models.CASCADE)
    lida = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        alvo = self.destinatario.nome if self.destinatario else self.destinatario_perfil
        return f"Notificação para {alvo} - {self.remetente.nome}"
from django.db import models
from django.utils import timezone



class Despacho(models.Model):
    STATUS_CHOICES = (
        ('pendente', 'Pendente (Aguardando Presidente)'),
        ('aprovado', 'Aprovado pelo Presidente'),
        ('rejeitado', 'Rejeitado'),
        ('enviado', 'enviado'),
    )

    # Relacionamento central com a Pré-defesa [cite: 1]
    # Através da predefesa, acessamos: Estudante, Curso, Tema, Tutor e Júris
    predefesa = models.OneToOneField(
        'Predefesa', 
        on_delete=models.CASCADE, 
        related_name='despacho_vinculado',
        help_text="Selecione a Pré-defesa para extrair os dados do Estudante e Júri"
    )

    # --- Identificação do Documento (Cabeçalho do PDF) ---
    numero_despacho = models.CharField(
        max_length=50, 
        help_text="Ex: 045/G.P/ISP-BI/01/2026"
    )
    ano_letivo = models.PositiveIntegerField(default=current_year)

    # --- Referências Legais (Padrão ISP-BI conforme Modelo) ---
    referencia_legal_1 = models.CharField(
        max_length=255, 
        default="art. 48 do Decreto Presidencial nº 193/18 de 10 de Agosto"
    )
    referencia_legal_2 = models.CharField(
        max_length=255, 
        default="alínea n) do art. 51 do Decreto Presidencial nº 310/20 de 7 de Dezembro"
    )

    # --- Dados de Localização e Emissão ---
    local_desenvolvimento = models.CharField(
        max_length=255,
        help_text="Instituição/Local onde o tema foi aplicado"
    )
    local_emissao = models.CharField(
        max_length=100, 
        default="Cuito"
    )
    data_emissao = models.DateField(
        default=timezone.now
    )

    # --- Fluxo de Aprovação e Assinatura ---
    status = models.CharField(
        max_length=20, 
        choices=STATUS_CHOICES, 
        default='pendente'
    )
    aprovado_por = models.ForeignKey(
        'Usuario', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        limit_choices_to={'perfil': 'presidente'},
        related_name='despachos_assinados'
    )
    publicado = models.BooleanField(
        default=False,
        help_text="Se marcado, o despacho fica visível e entra em vigor"
    )

    # --- Metadados de Gestão ---
    criado_por = models.ForeignKey(
        'Usuario', 
        on_delete=models.SET_NULL, 
        null=True,
        limit_choices_to={'perfil': 'area_cientifica'},
        related_name='despachos_preparados'
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Despacho de Nomeação de Júri"
        verbose_name_plural = "Despachos de Nomeação de Júri"
        ordering = ['-criado_em']

    def __str__(self):
        return f"Despacho {self.numero_despacho} - {self.predefesa.estudante.nome}"

class NotificacaoPredefesa(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificacoes_predefesa')
    mensagem = models.TextField()
    data_agendada = models.DateField()
    hora_agendada = models.TimeField()
    criado_em = models.DateTimeField(auto_now_add=True)
    lida = models.BooleanField(default=False)

    def __str__(self):
        return f"Notificação para {self.usuario.nome} - {self.data_agendada}"
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class SolicitacaoDefesa(models.Model):
    # Relacionamento com a Predefesa para obter os dados do Júri e Estudante
    predefesa = models.OneToOneField(
        'Predefesa', 
        on_delete=models.CASCADE, 
        related_name='solicitacao_defesa',
        help_text="Vincula o parecer do júri e os dados do estudante"
    )

    assunto = models.CharField(
        max_length=255, 
        default="Pedido de autorização para a apresentação e defesa pública de Trabalho de Fim de Curso"
    )

    local_defesa = models.CharField(
        max_length=200, 
        default="Auditório nº 1 do Instituto Superior Politécnico do Bié"
    )

    data_defesa = models.DateField(help_text="Data marcada para a defesa")
    hora_defesa = models.TimeField(help_text="Hora marcada para a defesa")

    chefe_departamento = models.ForeignKey(
        'Usuario',
        on_delete=models.PROTECT,
        limit_choices_to={'perfil': 'cordenacao'},
        related_name='solicitacoes_assinadas'
    )

    criado_em = models.DateTimeField(auto_now_add=True)
    status_solicitacao = models.CharField(
        max_length=20,
        choices=(
            ('pendente', 'Pendente'),
            ('autorizada', 'Autorizada pelo Presidente'),
            ('rejeitada', 'Rejeitada'),
        ),
        default='pendente'
    )

    class Meta:
        verbose_name = "Solicitação de Defesa de TFC"
        verbose_name_plural = "Solicitações de Defesa de TFC"

    def clean(self):
        """
        Valida se a solicitação está sendo feita dentro do período do processo
        aberto pelo coordenador para o curso do estudante.
        """
        super().clean()
        
        # Acessamos o curso através de: Solicitacao -> Predefesa -> Estudante -> Curso
        if self.predefesa and self.predefesa.estudante and self.predefesa.estudante.curso:
            hoje = timezone.now().date()
            curso_alvo = self.predefesa.estudante.curso
            
            processo = ProcessoEtapa.objects.filter(
                curso=curso_alvo,
                ativo=True,
                data_inicio__lte=hoje,
                data_termino__gte=hoje
            ).first()

            if not processo:
                raise ValidationError(
                    f"Ação bloqueada: O período para solicitações de defesa do curso "
                    f"{curso_alvo.nome} não está aberto ou já expirou."
                )

    def save(self, *args, **kwargs):
        # Força a validação do método clean() antes de persistir no banco
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Solicitação Defesa - {self.predefesa.estudante.nome}"

    @property
    def co_tutor(self):
        """Retorna vazio conforme solicitado."""
        return ""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class ActaDefesa(models.Model):
    # Relacionamento com a Solicitação (que já traz Estudante, Tema e Júri)
    solicitacao = models.OneToOneField(
        'SolicitacaoDefesa',
        on_delete=models.CASCADE,
        related_name='acta_final'
    )

    # Identificação da Acta 
    numero_acta = models.CharField(max_length=50, help_text="Ex: 001/2026")
    data_sessao = models.DateField()
    local_sessao = models.CharField(max_length=255, default="Instituto Superior Politécnico do Bié")

    # Horários da Sessão Pública 
    hora_abertura = models.TimeField(help_text="Início da sessão pública")
    hora_encerramento = models.TimeField(help_text="Encerramento da sessão")

    # Conteúdo da Avaliação 
    pontos_fortes = models.TextField(blank=True, null=True)
    pontos_fracos = models.TextField(blank=True, null=True)
    
    # Notas (Valores de 0 a 20) 
    avaliacao_sessao = models.DecimalField(max_digits=4, decimal_places=2, help_text="Avaliação da sessão")
    avaliacao_final = models.DecimalField(max_digits=4, decimal_places=2, help_text="Avaliação Final")
    
    observacoes = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Acta da Sessão de Defesa"
        verbose_name_plural = "Actas das Sessões de Defesa"

    def clean(self):
        """
        Verifica se a Acta está sendo gerada dentro do período de processo
        aberto pelo coordenador para o curso do estudante.
        """
        super().clean()
        
        # O caminho para o curso é: Acta -> Solicitação -> Predefesa -> Estudante -> Curso
        if self.solicitacao and self.solicitacao.predefesa.estudante.curso:
            hoje = timezone.now().date()
            curso_estudante = self.solicitacao.predefesa.estudante.curso
            
            processo = ProcessoEtapa.objects.filter(
                curso=curso_estudante,
                ativo=True,
                data_inicio__lte=hoje,
                data_termino__gte=hoje
            ).first()

            if not processo:
                raise ValidationError(
                    f"Erro de Integridade: Não é possível registrar actas fora do período "
                    f"do processo ativo para o curso {curso_estudante.nome}."
                )

    def save(self, *args, **kwargs):
        # Validação total antes de salvar a nota final
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Acta {self.numero_acta} - {self.solicitacao.predefesa.estudante.nome}"

    # Propriedades para preenchimento automático
    @property
    def estudante(self):
        return self.solicitacao.predefesa.estudante

    @property
    def tema(self):
        return self.solicitacao.predefesa.tema

    @property
    def presidente(self):
        return self.solicitacao.predefesa.presidente


from django.db import models

class ListaTemasAprovados(models.Model):
    STATUS_ENVIO = (
        ('nao_enviado', 'Aguardando Envio'),
        ('enviado', 'Enviado para Área Científica'),
        ('recebido', 'Recebido pela Área Científica'),
    )

    # Identificação da Lista
    codigo_referencia = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Código da Lista",
        help_text="Ex: LISTA-2026-ENG-001"
    )
    
    # Relacionamos com os temas que foram aprovados
    # Usamos ManyToMany para que uma lista contenha vários temas
    temas = models.ManyToManyField(
        'Tema', 
        related_name='listas_aprovadas',
        limit_choices_to={'status_final': 'aprovado'},
        verbose_name="Temas Aprovados"
    )

    # Controle de Fluxo
    status = models.CharField(
        max_length=20, 
        choices=STATUS_ENVIO, 
        default='nao_enviado'
    )
    
    # Responsável pelo envio (Coordenador)
    enviado_por = models.ForeignKey(
        'Usuario', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='listas_enviadas'
    )

    # Metadados
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_envio = models.DateTimeField(null=True, blank=True)
    observacoes = models.TextField(blank=True, null=True, help_text="Notas para a Área Científica")

    class Meta:
        verbose_name = "Lista de Temas Aprovados"
        verbose_name_plural = "Listas de Temas Aprovados"
        ordering = ['-data_criacao']

    def __str__(self):
        return f"{self.codigo_referencia} - {self.get_status_display()}"

    def enviar_para_area_cientifica(self):
        """Método para marcar como enviado e registrar a data"""
        from django.utils import timezone
        self.status = 'enviado'
        self.data_envio = timezone.now()
        self.save()

from django.db import models

class ListaPreDefesas(models.Model):
    STATUS_ENVIO = (
        ('nao_enviado', 'Não Enviado'),
        ('enviado', 'Enviado'),
    )

    # 1. Atributo: Lista de pré-defesas (Relacionamento)
    predefesas = models.ManyToManyField('Predefesa', related_name='listas')

    # 2. Atributo: Status
    status = models.CharField(
        max_length=20, 
        choices=STATUS_ENVIO, 
        default='nao_enviado'
    )

    data_criacao = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Remessa {self.id} - {self.get_status_display()}"


class NotificacaoFinal(models.Model):
    TIPOS = (
        ('info', 'Informação'),
        ('sucesso', 'Sucesso/Concluído'),
        ('alerta', 'Alerta/Atenção'),
    )

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificacoesfinais')
    titulo = models.CharField(max_length=150)
    mensagem = models.TextField()
    lida = models.BooleanField(default=False)
    criada_em = models.DateTimeField(auto_now_add=True)
    # Campo adicionado para suportar links
    link = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['-criada_em']

    def __str__(self):
        return f"Notificação para {self.usuario.username} - {self.titulo}"
from django.db import models
from django.utils import timezone

class CalendarioAprovacao(models.Model):
    PERIODO_CHOICES = (
        ('regular', 'Regular'),
        ('poslaboral', 'Pós-Laboral'),
    )

    titulo = models.CharField(max_length=200, help_text="Ex: Aprovação de Temas - 2º Semestre")
    data_aprovacao = models.DateTimeField(verbose_name="Data e Hora da Aprovação")
    periodo = models.CharField(max_length=20, choices=PERIODO_CHOICES, verbose_name="Período")
    curso = models.ForeignKey('Curso', on_delete=models.CASCADE, related_name="calendarios_aprovacao")
    ativo = models.BooleanField(default=True, help_text="Se ativo, a notificação será disparada")

    class Meta:
        verbose_name = "Calendário de Aprovação"
        verbose_name_plural = "Calendários de Aprovação"

    def __str__(self):
        return f"{self.titulo} - {self.get_periodo_display()} ({self.data_aprovacao.strftime('%d/%m/%Y %H:%M')})"

class RegistoBackup(models.Model):
    """Histórico das cópias de segurança feitas pelo administrador."""

    utilizador = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="backups_feitos"
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    nome_ficheiro = models.CharField(max_length=120)
    registos = models.PositiveIntegerField(default=0)
    ficheiros = models.PositiveIntegerField(default=0)
    tamanho = models.PositiveBigIntegerField(default=0, help_text="Tamanho do ZIP em bytes")
    incluiu_media = models.BooleanField(default=False)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Registo de cópia de segurança"
        verbose_name_plural = "Registos de cópias de segurança"

    def __str__(self):
        return f"{self.nome_ficheiro} ({self.criado_em:%d/%m/%Y %H:%M})"
