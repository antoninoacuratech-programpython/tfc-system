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

def filtro_tutores():
    """Quem pode orientar ou estar numa banca: perfil tutor ou tutor como perfil adicional."""
    from django.db.models import Q
    return Q(perfil="tutor") | Q(pk__in=PerfilAdicional.objects.filter(perfil="tutor").values("usuario_id"))


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

    @property
    def perfil_principal(self):
        # durante o pedido o «perfil» é o perfil activo da sessão; o gravado na base é este
        return getattr(self, "_perfil_principal", None) or self.perfil

    @property
    def perfis_disponiveis(self):
        if not hasattr(self, "_cache_perfis"):
            extras = [p for p in self.perfis_adicionais.values_list("perfil", flat=True)] if self.pk else []
            self._cache_perfis = list(dict.fromkeys([self.perfil_principal, *extras]))
        return self._cache_perfis

    def tem_papel(self, perfil):
        return perfil in self.perfis_disponiveis

    def ativar_perfil(self, perfil):
        """Troca o perfil activo só neste objecto (a sessão guarda a escolha)."""
        if perfil not in self.perfis_disponiveis:
            return False
        if not hasattr(self, "_perfil_principal"):
            self._perfil_principal = self.perfil
        self.perfil = perfil
        return True

    def save(self, *args, **kwargs):
        # nunca gravar o perfil activo por cima do principal
        principal = getattr(self, "_perfil_principal", None)
        if principal is None or principal == self.perfil:
            return super().save(*args, **kwargs)
        ativo, self.perfil = self.perfil, principal
        try:
            return super().save(*args, **kwargs)
        finally:
            self.perfil = ativo

    def obter_todos_documentos(self):
        docs = []

        for i in self.inscricoes_tfc.all():
            if i.requerimento: docs.append({'nome': 'Inscrição: Requerimento', 'url': i.requerimento.url})
            if i.curriculum_academico: docs.append({'nome': 'Inscrição: Currículo', 'url': i.curriculum_academico.url})
            if i.copia_bi: docs.append({'nome': 'Inscrição: Cópia BI', 'url': i.copia_bi.url})

        for t in self.temas.all():
            if t.resumo: docs.append({'nome': 'Tema: Resumo', 'url': t.resumo.url})
            if t.requerimento: docs.append({'nome': 'Tema: Requerimento', 'url': t.requerimento.url})

        for pd in self.minhas_predefesas.all():
            if hasattr(pd, 'solicitacao_defesa'):
                docs.append({'nome': 'Solicitação de Defesa', 'url': '#'})
                
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

    estudante = models.ForeignKey(
        'Usuario',
        on_delete=models.CASCADE,
        related_name='temas',
        limit_choices_to={'perfil': 'estudante'}
    )
    
    processo = models.ForeignKey(
        'ProcessoEtapa',
        on_delete=models.CASCADE,
        related_name='temas_vinculados',
        verbose_name="Processo de Origem",
        help_text="Processo ativo no momento da submissão",
        null=True,
        blank=True
    )

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
        limit_choices_to=filtro_tutores
    )

    status_tutor = models.CharField(max_length=15, choices=STATUS_TUTOR, default='pendente')
    status_coordenacao = models.CharField(max_length=20, choices=STATUS_COORD, default='pendente')
    status_final = models.CharField(max_length=15, choices=STATUS_FINAL, default='pendente')

    data_envio = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Tema"
        verbose_name_plural = "Temas"
        ordering = ['-data_envio']

    def clean(self):
        super().clean()
        
        if self.estudante and hasattr(self.estudante, 'curso') and self.estudante.curso:
            hoje = timezone.now().date()
            
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
            
            self.processo = processo_ativo
        else:
            raise ValidationError("O estudante precisa estar vinculado a um curso para criar um tema.")

    def save(self, *args, **kwargs):
        if not self.pk:
            self.full_clean()

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
        limit_choices_to=filtro_tutores,
        related_name='recomendacoes_feitas'
    )
    texto = models.TextField()
    lida = models.BooleanField(default=False)
    data_criacao = models.DateTimeField(auto_now_add=True)
    data_atualizacao = models.DateTimeField(auto_now=True)

    TIPOS = (("melhoria", "A melhorar"), ("forte", "Ponto forte"))
    ESTADOS = (("pendente", "Pendente"), ("resolvida", "Resolvida pelo estudante"), ("cumprida", "Cumprida"))

    # recomendações da banca ficam ligadas à pré-defesa; as do tutor não têm pré-defesa
    predefesa = models.ForeignKey('Predefesa', on_delete=models.CASCADE, null=True, blank=True, related_name='recomendacoes')
    autor = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='recomendacoes_autor')
    funcao_autor = models.CharField(max_length=30, blank=True)
    tipo = models.CharField(max_length=10, choices=TIPOS, default="melhoria")
    estado = models.CharField(max_length=10, choices=ESTADOS, default="pendente")
    nota_estudante = models.TextField(blank=True)
    resolvida_em = models.DateTimeField(null=True, blank=True)
    cumprida_em = models.DateTimeField(null=True, blank=True)
    cumprida_por = models.ForeignKey('Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='+')

    class Meta:
        ordering = ['-data_criacao']
        verbose_name = "Recomendação"
        verbose_name_plural = "Recomendações"

    @property
    def cumprida(self):
        return self.estado == "cumprida"

    @property
    def acompanhavel(self):
        return self.tipo == "melhoria"

    def clean(self):
        super().clean()

        # só se exige processo aberto para o tutor criar recomendações novas
        if not self._state.adding or self.predefesa_id:
            return
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
        limit_choices_to=filtro_tutores,
        related_name='atuacoes_secretario'
    )

    presidente = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE, 
        limit_choices_to=filtro_tutores, related_name='presidencias'
    )
    primeiro_vogal = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE, 
        limit_choices_to=filtro_tutores, related_name='vogal1_atuacoes'
    )
    segundo_vogal = models.ForeignKey(
        'Usuario', on_delete=models.CASCADE, 
        limit_choices_to=filtro_tutores, related_name='vogal2_atuacoes'
    )

    RESULTADOS = (
        ("apto", "Apto"),
        ("apto_recomendacoes", "Apto com recomendações"),
        ("nao_apto", "Não apto"),
    )
    # sessão: alterada com update() para não voltar a validar o agendamento
    aberta_em = models.DateTimeField(null=True, blank=True)
    presentes = models.JSONField(default=list, blank=True)
    encerrada_em = models.DateTimeField(null=True, blank=True)
    resultado = models.CharField(max_length=20, choices=RESULTADOS, blank=True)
    observacoes_sessao = models.TextField(blank=True)

    def mesa(self):
        """Lista (função, chave, docente) pela ordem de apresentação."""
        return [
            ("Presidente", "presidente", self.presidente),
            ("Secretário", "secretario", self.secretario),
            ("1.º vogal", "primeiro_vogal", self.primeiro_vogal),
            ("2.º vogal", "segundo_vogal", self.segundo_vogal),
        ]

    def funcao_de(self, usuario):
        for nome, _, docente in self.mesa():
            if docente and usuario and docente.pk == usuario.pk:
                return nome
        return ""

    def clean(self):
        super().clean()
        if not self.estudante:
            return

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
        
        tema_obj = Tema.objects.filter(estudante=self.estudante).order_by('-data_envio').first()
        if not tema_obj:
            raise ValidationError(f"O estudante {self.estudante} não possui um tema registrado.")
        
        self.tema = tema_obj
        tutor_do_estudante = tema_obj.tutor_indicado
        
        juris_selecionados = [self.presidente, self.primeiro_vogal, self.segundo_vogal, self.secretario]

        # o mesmo docente não pode ocupar duas funções na mesa
        ids_juri = [j.pk for j in juris_selecionados if j is not None]
        if len(ids_juri) != len(set(ids_juri)):
            raise ValidationError(
                "O mesmo docente não pode ocupar mais de uma função na mesa de júri "
                "(presidente, secretário, 1º vogal e 2º vogal devem ser pessoas diferentes)."
            )

        for juri in juris_selecionados:
            if juri == tutor_do_estudante:
                raise ValidationError(f"Conflito: O orientador {juri} não pode fazer parte da Mesa de Júri deste estudante.")
        
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


# tem de ser uma função com nome, senão o makemigrations gera uma migração nova sempre
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

    estudante = models.ForeignKey('Usuario', on_delete=models.CASCADE, related_name='inscricoes_tfc')
    tema = models.OneToOneField('Tema', on_delete=models.CASCADE, related_name='ficha_inscricao')
    enviado_para_coordenacao = models.BooleanField(default=False)
    periodo = models.CharField(max_length=20, choices=PERIODO_CHOICES, default='Regular')
    nacionalidade = models.CharField(max_length=50, default="Angolana")
    endereco = models.CharField(max_length=255)
    local_desenvolvimento = models.CharField(max_length=255)
    ano_conclusao_curriculo = models.PositiveIntegerField(default=current_year)
    
    requerimento = models.FileField(upload_to='tfc/requerimentos/', null=True, blank=True)
    curriculum_academico = models.FileField(upload_to='tfc/curriculos/', null=True, blank=True)
    ficha_reconfirmacao = models.FileField(upload_to='tfc/fichas/', null=True, blank=True)
    comprovativo_pagamento = models.FileField(upload_to='tfc/pagamentos/', null=True, blank=True)
    copia_bi = models.FileField(upload_to='tfc/documentos_id/', null=True, blank=True)

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='pendente')
    aprovado_por = models.ForeignKey(
        'Usuario', on_delete=models.SET_NULL, null=True, blank=True, related_name='validador_tfc'
    )
    data_criacao = models.DateTimeField(auto_now_add=True)

    def clean(self):
        super().clean()
        
        if self.estudante and self.estudante.curso:
            hoje = timezone.now().date()
            
            from .models import ProcessoEtapa
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
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Ficha {self.id} - {self.estudante.nome}"

class NotificacaoTFC(models.Model):
    remetente = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificacoes_enviadas')
    
    destinatario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name='notificacoes_recebidas', null=True, blank=True)
    
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

    predefesa = models.OneToOneField(
        'Predefesa', 
        on_delete=models.CASCADE, 
        related_name='despacho_vinculado',
        help_text="Selecione a Pré-defesa para extrair os dados do Estudante e Júri"
    )

    numero_despacho = models.CharField(
        max_length=50, 
        help_text="Ex: 045/G.P/ISP-BI/01/2026"
    )
    ano_letivo = models.PositiveIntegerField(default=current_year)

    referencia_legal_1 = models.CharField(
        max_length=255, 
        default="art. 48 do Decreto Presidencial nº 193/18 de 10 de Agosto"
    )
    referencia_legal_2 = models.CharField(
        max_length=255, 
        default="alínea n) do art. 51 do Decreto Presidencial nº 310/20 de 7 de Dezembro"
    )

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
        super().clean()
        
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
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Solicitação Defesa - {self.predefesa.estudante.nome}"

    @property
    def co_tutor(self):
        return ""

from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone

class ActaDefesa(models.Model):
    solicitacao = models.OneToOneField(
        'SolicitacaoDefesa',
        on_delete=models.CASCADE,
        related_name='acta_final'
    )

    numero_acta = models.CharField(max_length=50, help_text="Ex: 001/2026")
    data_sessao = models.DateField()
    local_sessao = models.CharField(max_length=255, default="Instituto Superior Politécnico do Bié")

    hora_abertura = models.TimeField(help_text="Início da sessão pública")
    hora_encerramento = models.TimeField(help_text="Encerramento da sessão")

    pontos_fortes = models.TextField(blank=True, null=True)
    pontos_fracos = models.TextField(blank=True, null=True)
    
    avaliacao_sessao = models.DecimalField(max_digits=4, decimal_places=2, help_text="Avaliação da sessão")
    avaliacao_final = models.DecimalField(max_digits=4, decimal_places=2, help_text="Avaliação Final")
    
    observacoes = models.TextField(blank=True, null=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Acta da Sessão de Defesa"
        verbose_name_plural = "Actas das Sessões de Defesa"

    def clean(self):
        super().clean()
        
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
        self.full_clean()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Acta {self.numero_acta} - {self.solicitacao.predefesa.estudante.nome}"

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

    codigo_referencia = models.CharField(
        max_length=50, 
        unique=True, 
        verbose_name="Código da Lista",
        help_text="Ex: LISTA-2026-ENG-001"
    )
    
    temas = models.ManyToManyField(
        'Tema', 
        related_name='listas_aprovadas',
        limit_choices_to={'status_final': 'aprovado'},
        verbose_name="Temas Aprovados"
    )

    status = models.CharField(
        max_length=20, 
        choices=STATUS_ENVIO, 
        default='nao_enviado'
    )
    
    enviado_por = models.ForeignKey(
        'Usuario', 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True,
        related_name='listas_enviadas'
    )

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

    predefesas = models.ManyToManyField('Predefesa', related_name='listas')

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


class TemaSugerido(models.Model):
    ESTADOS = (
        ("aberto", "Aberto"),
        ("fechado", "Fechado"),
    )

    titulo = models.CharField(max_length=200)
    descricao = models.TextField(help_text="Objetivos e o que se espera do trabalho")
    curso = models.ForeignKey(Curso, on_delete=models.CASCADE, related_name="temas_sugeridos")
    tutor_sugerido = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="temas_sugeridos_orientar", limit_choices_to={"perfil": "tutor"},
    )
    criado_por = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="temas_sugeridos_criados",
    )
    estado = models.CharField(max_length=10, choices=ESTADOS, default="aberto")
    # tema criado quando um estudante escolhe a sugestão
    tema = models.OneToOneField(Tema, on_delete=models.SET_NULL, null=True, blank=True, related_name="sugestao")
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-criado_em"]
        verbose_name = "Tema sugerido"
        verbose_name_plural = "Temas sugeridos"

    def __str__(self):
        return self.titulo

    @property
    def escolhido(self):
        # se a coordenação ou o tutor rejeitarem, a sugestão volta a ficar livre
        return bool(
            self.tema_id
            and self.tema.status_coordenacao != "rejeitado"
            and self.tema.status_tutor != "rejeitado"
        )

    @property
    def disponivel(self):
        return self.estado == "aberto" and not self.escolhido


class ResumoIA(models.Model):
    tema = models.OneToOneField(Tema, on_delete=models.CASCADE, related_name="resumo_ia")
    conteudo = models.JSONField()
    gerado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    gerado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Resumo para o júri (IA)"
        verbose_name_plural = "Resumos para o júri (IA)"

    def __str__(self):
        return f"Resumo IA — {self.tema.titulo}"


class PlanoTrabalho(models.Model):
    tema = models.OneToOneField(Tema, on_delete=models.CASCADE, related_name="plano")
    criado_em = models.DateTimeField(auto_now_add=True)
    ultimo_alerta_parado = models.DateField(null=True, blank=True)

    class Meta:
        verbose_name = "Plano de trabalho"
        verbose_name_plural = "Planos de trabalho"

    def __str__(self):
        return f"Plano — {self.tema.titulo}"


class EtapaTrabalho(models.Model):
    ESTADOS = (
        ("pendente", "Por entregar"),
        ("entregue", "Entregue"),
        ("revisao", "A rever"),
        ("aprovada", "Aprovada"),
    )

    plano = models.ForeignKey(PlanoTrabalho, on_delete=models.CASCADE, related_name="etapas")
    ordem = models.PositiveIntegerField(default=1)
    titulo = models.CharField(max_length=150)
    descricao = models.TextField(blank=True)
    prazo = models.DateField()
    estado = models.CharField(max_length=10, choices=ESTADOS, default="pendente")
    ficheiro = models.FileField(upload_to="etapas/", null=True, blank=True)
    comentario_estudante = models.TextField(blank=True)
    comentario_tutor = models.TextField(blank=True)
    entregue_em = models.DateTimeField(null=True, blank=True)
    avaliada_em = models.DateTimeField(null=True, blank=True)
    alerta_prazo_enviado = models.BooleanField(default=False)
    alerta_atraso_enviado = models.BooleanField(default=False)

    class Meta:
        ordering = ["ordem", "prazo", "pk"]
        verbose_name = "Etapa do trabalho"
        verbose_name_plural = "Etapas do trabalho"

    def __str__(self):
        return f"{self.ordem}. {self.titulo}"

    @property
    def por_entregar(self):
        return self.estado in ("pendente", "revisao")

    @property
    def atrasada(self):
        from django.utils import timezone
        return self.por_entregar and self.prazo < timezone.localdate()


class Ficheiro(models.Model):
    """Conteúdo dos ficheiros carregados, guardado na base de dados (ver armazenamento.py)."""

    nome = models.CharField(max_length=255, unique=True)
    conteudo = models.BinaryField()
    tamanho = models.PositiveIntegerField(default=0)
    tipo = models.CharField(max_length=100, blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Rubrica(models.Model):
    """Imagem da assinatura manuscrita de um utilizador (PNG, já limpo e redimensionado)."""

    usuario = models.OneToOneField(Usuario, on_delete=models.CASCADE, related_name="rubrica")
    imagem = models.BinaryField()
    atualizada_em = models.DateTimeField(auto_now=True)


class DocumentoAssinado(models.Model):
    TIPOS = (("declaracao_orientador", "Declaração de responsabilidade do orientador"),)

    codigo = models.CharField(max_length=16, unique=True)
    tipo = models.CharField(max_length=40, choices=TIPOS, default="declaracao_orientador")
    tema = models.ForeignKey(Tema, on_delete=models.CASCADE, related_name="documentos_assinados")
    assinante = models.ForeignKey(Usuario, on_delete=models.PROTECT, related_name="documentos_assinados")
    assinado_em = models.DateTimeField()
    impressao = models.CharField(max_length=64, help_text="SHA-256 do conteúdo assinado")
    visto_por = models.ForeignKey(Usuario, on_delete=models.PROTECT, null=True, blank=True, related_name="vistos_dados")
    visto_em = models.DateTimeField(null=True, blank=True)
    anulado_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-assinado_em"]

    def __str__(self):
        return f"{self.get_tipo_display()} · {self.codigo}"

    @property
    def valido(self):
        return self.anulado_em is None



class PerfilAdicional(models.Model):
    """Funções acumuladas: p. ex. um coordenador que também orienta trabalhos."""

    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, related_name="perfis_adicionais")
    perfil = models.CharField(max_length=20, choices=Usuario.TIPOS_USUARIO)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("usuario", "perfil")
        verbose_name = "Perfil adicional"
        verbose_name_plural = "Perfis adicionais"

    def __str__(self):
        return f"{self.usuario} · {self.perfil}"


def tutores():
    return Usuario.objects.filter(filtro_tutores())
