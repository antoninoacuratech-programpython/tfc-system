"""Views da aplicação Coordenacao, organizadas por área funcional."""
from .autenticacao import (  # noqa: F401
    login_view,
    sair,
    cadastro,
    atualizar_perfil,
    escolher_perfil,
    definir_senha,
)
from .dashboards import (  # noqa: F401
    admink,
    dashboard_estudante,
    dashboard_tutor,
    dashboard_presidencia,
    index_area_cientifica,
    index_area_etica,
)
from .temas import (  # noqa: F401
    lista_estudantes,
    alterar_status_tema,
    get_temas_filtrados,
    temas_aprovados,
    temas_reprovados,
    alterar_status_multiplos,
    criar_ou_editar_tema,
    alterar_status_tema_tutor,
    alterar_status_multiplos_tutor,
    lista_todos_temas_geral,
    adicionar_orientador,
    area_cientifica_temas,
    gerar_buffer_listagem_temas,
    exportar_todos_temas_pdf,
    despachar_para_cientifica,
)
from .recomendacoes import (  # noqa: F401
    adicionar_recomendacao,
    todas_recomendacoes,
    baixar_recomendacoes_pdf,
)
from .utilizadores import (  # noqa: F401
    add_estudante,
    alterar_estado_multiplos_usuarios,
    gerenciar_professores,
    editar_professor,
    alternar_status_professor,
    eliminar_professor,
    lista_estudantes_tutor,
)
from .estrutura import (  # noqa: F401
    lista_departamentos,
    criar_departamento,
    editar_departamento,
    excluir_departamento,
    lista_cursos,
    criar_curso,
    editar_curso,
    excluir_curso,
)
from .predefesas import (  # noqa: F401
    agendar_predefesa,
    lista_predefesas,
    gerar_pdf_predefesa,
    gerar_pdf_todas_predefesas,
    despachar_predefesas_cientifica,
    lista_cursos_predefesas,
    predefesas_por_curso,
    editar_predefesa,
    eliminar_predefesa,
    buscar_predefesas_por_curso,
)
from .comunicados import (  # noqa: F401
    criar_comunicado,
    lista_comunicados,
    atualizar_comunicado,
    eliminar_comunicado,
    publicar_comunicado,
    texto_comunicado_oficial,
    gerar_comunicado_pdf,
    baixar_comunicado_pdf,
)
from .inscricoes import (  # noqa: F401
    lista_inscricoes_tfc,
    gerar_ficha_tfc,
    editar_inscricao_tfc,
    baixar_pdf_tfc,
    lista_inscricoes_pendentes,
    lista_cursos_fichas_pendentes,
    fichas_pendentes_por_curso,
    historico_inscricoes,
    aprovar_inscricao_tfc,
    rejeitar_inscricao_tfc,
    lista_inscricoes_aprovadas_coordenacao,
    enviar_para_coordenacao,
)
from .despachos import (  # noqa: F401
    gerar_buffer_despacho,
    gerar_despacho_pdf,
    baixar_todos_despachos_zip,
    criar_despacho,
    enviar_despacho_presidencia,
    assinar_despacho,
    listar_despachos,
    eliminar_despacho,
)
from .defesas import (  # noqa: F401
    lista_solicitacoes_defesa,
    detalhes_solicitacao_defesa,
    criar_solicitacao_defesa,
    extrair_logica_pdf_solicitacao,
    gerar_pdf_solicitacao,
    baixar_todas_solicitacoes_zip,
    criar_acta,
    gerar_conteudo_pdf_acta,
    baixar_acta_pdf,
    baixar_todas_actas_zip,
    lista_actas,
    detalhe_acta,
)
from .processos import (  # noqa: F401
    lista_processos,
    criar_processo,
    alternar_status_processo,
    editar_processo,
    eliminar_processo,
    gerir_calendarios,
)
from .notificacoes import (  # noqa: F401
    ver_notificacao,
    listar_notificacoes,
    marcar_notificacao_lida,
)
from .backups import (  # noqa: F401
    backups,
    criar_backup,
)
from .sugestoes import (  # noqa: F401
    gerir_sugestoes,
    editar_sugestao,
    alternar_sugestao,
    eliminar_sugestao,
    sugestoes_estudante,
    escolher_sugestao,
)
from .ia import (  # noqa: F401
    ia_proposta,
    ia_analise,
    resumo_juri,
    minhas_bancas,
)
from .progresso import (  # noqa: F401
    meu_progresso,
    entregar_etapa,
    progresso_tutor,
    progresso_tema,
    criar_plano,
    guardar_etapa,
    eliminar_etapa,
    avaliar_etapa,
    progresso_geral,
)
from .ficheiros import servir_ficheiro  # noqa: F401
from .assinaturas import (  # noqa: F401
    gerar_pdf_declaracao_orientador,
    assinar_declaracao,
    anular_assinatura,
    vistos_declaracoes,
    dar_visto,
    minha_rubrica,
    verificar_documento,
)
from .recomendacoes import mudar_estado_recomendacao  # noqa: F401
from .sessao_predefesa import (  # noqa: F401
    sessao_predefesa,
    abrir_sessao_predefesa,
    registar_recomendacao_banca,
    eliminar_recomendacao_banca,
    encerrar_sessao_predefesa,
)
from .processo_estudante import (  # noqa: F401
    processo_estudante,
    processo_estudante_zip,
    perfil_documental,
)
from .utilizadores import funcoes_acumuladas  # noqa: F401
from .importacao import importar_estudantes, modelo_importacao  # noqa: F401
