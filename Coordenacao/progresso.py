"""Progresso dos trabalhos (etapas com prazos) e alertas automáticos."""

import logging
from datetime import timedelta

from django.core.cache import cache
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

logger = logging.getLogger(__name__)

DIAS_AVISO_PRAZO = 3
DIAS_PARADO = 30

PLANO_PADRAO = [
    ("Introdução", "Contextualização, problema, objetivos e justificação."),
    ("Revisão bibliográfica", "Conceitos, trabalhos relacionados e enquadramento teórico."),
    ("Metodologia", "Abordagem, técnicas, ferramentas e forma de validação."),
    ("Desenvolvimento e resultados", "Implementação ou estudo e apresentação dos resultados."),
    ("Conclusão e versão final", "Conclusões, recomendações e documento completo para pré-defesa."),
]


def resumo(plano):
    """Números e estado de um plano: percentagem, atrasos, próxima etapa."""
    hoje = timezone.localdate()
    etapas = list(plano.etapas.all()) if plano else []
    total = len(etapas)
    aprovadas = sum(1 for e in etapas if e.estado == "aprovada")
    atrasadas = [e for e in etapas if e.atrasada]
    proxima = next((e for e in etapas if e.por_entregar), None)

    ultima = max((e.entregue_em for e in etapas if e.entregue_em), default=None)
    referencia = timezone.localtime(ultima).date() if ultima else (timezone.localtime(plano.criado_em).date() if plano else hoje)
    parado = bool(proxima) and (hoje - referencia).days >= DIAS_PARADO

    if not total:
        estado, rotulo = "sem_plano", "Sem plano"
    elif aprovadas == total:
        estado, rotulo = "concluido", "Concluído"
    elif parado:
        estado, rotulo = "parado", "Parado"
    elif atrasadas:
        estado, rotulo = "atrasado", "Atrasado"
    else:
        estado, rotulo = "em_dia", "Em dia"

    return {
        "total": total,
        "aprovadas": aprovadas,
        "percentagem": round(aprovadas * 100 / total) if total else 0,
        "atrasadas": len(atrasadas),
        "proxima": proxima,
        "dias_sem_atividade": (hoje - referencia).days,
        "estado": estado,
        "rotulo": rotulo,
    }


def _notificar(usuario, titulo, mensagem, link):
    from .models import NotificacaoFinal
    if usuario:
        NotificacaoFinal.objects.create(usuario=usuario, titulo=titulo, mensagem=mensagem, link=link)


def gerar_alertas(hoje=None):
    """Cria as notificações de prazos e de estudantes parados. Pode correr várias vezes: nunca repete."""
    from .models import EtapaTrabalho, PlanoTrabalho, Usuario

    hoje = hoje or timezone.localdate()
    contagem = {"prazo": 0, "atraso": 0, "parado": 0}

    proximas = EtapaTrabalho.objects.select_related("plano__tema__estudante", "plano__tema__tutor_indicado").filter(
        estado__in=("pendente", "revisao"), alerta_prazo_enviado=False,
        prazo__gte=hoje, prazo__lte=hoje + timedelta(days=DIAS_AVISO_PRAZO),
    )
    for etapa in proximas:
        with transaction.atomic():
            # marca primeiro: se outro processo já tratou desta etapa, não volta a avisar
            if not EtapaTrabalho.objects.filter(pk=etapa.pk, alerta_prazo_enviado=False).update(alerta_prazo_enviado=True):
                continue
            dias = (etapa.prazo - hoje).days
            quando = "hoje" if dias == 0 else "amanhã" if dias == 1 else f"em {dias} dias"
            _notificar(etapa.plano.tema.estudante, "Prazo a terminar",
                       f"A etapa «{etapa.titulo}» termina {quando} ({etapa.prazo:%d/%m/%Y}).",
                       reverse("meu_progresso"))
            contagem["prazo"] += 1

    atrasadas = EtapaTrabalho.objects.select_related("plano__tema__estudante", "plano__tema__tutor_indicado").filter(
        estado__in=("pendente", "revisao"), alerta_atraso_enviado=False, prazo__lt=hoje,
    )
    for etapa in atrasadas:
        with transaction.atomic():
            if not EtapaTrabalho.objects.filter(pk=etapa.pk, alerta_atraso_enviado=False).update(alerta_atraso_enviado=True):
                continue
            tema = etapa.plano.tema
            nome = f"{tema.estudante.nome} {tema.estudante.sobrenome}"
            _notificar(tema.estudante, "Etapa em atraso",
                       f"A etapa «{etapa.titulo}» tinha prazo a {etapa.prazo:%d/%m/%Y} e ainda não foi entregue.",
                       reverse("meu_progresso"))
            _notificar(tema.tutor_indicado, "Orientando com etapa em atraso",
                       f"{nome} ainda não entregou «{etapa.titulo}» (prazo {etapa.prazo:%d/%m/%Y}).",
                       reverse("progresso_tema", args=[tema.pk]))
            contagem["atraso"] += 1

    for plano in PlanoTrabalho.objects.select_related("tema__estudante__curso", "tema__tutor_indicado"):
        if plano.ultimo_alerta_parado and (hoje - plano.ultimo_alerta_parado).days < DIAS_PARADO:
            continue
        info = resumo(plano)
        if info["estado"] != "parado":
            continue
        if not PlanoTrabalho.objects.filter(pk=plano.pk, ultimo_alerta_parado=plano.ultimo_alerta_parado).update(ultimo_alerta_parado=hoje):
            continue
        tema = plano.tema
        nome = f"{tema.estudante.nome} {tema.estudante.sobrenome}"
        mensagem = f"{nome} não entrega nenhuma etapa do TFC há {info['dias_sem_atividade']} dias («{tema.titulo}»)."
        link = reverse("progresso_tema", args=[tema.pk])
        _notificar(tema.tutor_indicado, "Estudante parado", mensagem, link)
        if tema.estudante.curso_id:
            for coord in Usuario.objects.filter(perfil="cordenacao", curso_id=tema.estudante.curso_id, estado_user="activo"):
                _notificar(coord, "Estudante parado", mensagem, link)
        contagem["parado"] += 1

    if any(contagem.values()):
        logger.info("Alertas de progresso: %s", contagem)
    return contagem


def alertas_do_dia():
    """Corre gerar_alertas() no máximo uma vez por dia (chamado ao abrir as páginas do sistema)."""
    chave = f"alertas-progresso:{timezone.localdate():%Y%m%d}"
    if cache.add(chave, True, 60 * 60 * 26):
        try:
            gerar_alertas()
        except Exception:
            cache.delete(chave)
            logger.exception("Falha ao gerar alertas de progresso")
