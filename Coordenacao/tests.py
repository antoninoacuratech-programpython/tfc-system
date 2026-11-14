"""Testes de acesso e renderização das páginas principais do SGTF."""

from django.test import TestCase
from django.urls import reverse

from .models import Curso, Departamento, Usuario


class BaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.departamento = Departamento.objects.create(nome="Informática")
        cls.curso = Curso.objects.create(nome="Engenharia Informática", departamento=cls.departamento)

        def criar(email, perfil, **extra):
            return Usuario.objects.create_user(
                email=email, password="SenhaForte#2026", nome="Teste", sobrenome=perfil.title(),
                telefone="923000000", perfil=perfil, estado_user="activo", curso=cls.curso, **extra
            )

        cls.estudante = criar("estudante@ispb.ao", "estudante")
        cls.outro_estudante = criar("outro@ispb.ao", "estudante")
        cls.tutor = criar("tutor@ispb.ao", "tutor")
        cls.coordenacao = criar("coord@ispb.ao", "cordenacao")
        cls.cientifica = criar("ac@ispb.ao", "area_cientifica")
        cls.presidente = criar("pres@ispb.ao", "presidente")


class AutenticacaoTests(BaseTestCase):
    def test_pagina_login_renderiza(self):
        resposta = self.client.get(reverse("login"))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Entrar")

    def test_login_redirecciona_para_painel_do_perfil(self):
        casos = {
            "estudante@ispb.ao": "dashboard_estudante",
            "tutor@ispb.ao": "dashboard_tutor",
            "coord@ispb.ao": "admink",
            "ac@ispb.ao": "index_area_cientifica",
            "pres@ispb.ao": "dashboard_presidencia",
        }
        for email, destino in casos.items():
            with self.subTest(email=email):
                self.client.logout()
                resposta = self.client.post(reverse("login"), {"username": email, "senha": "SenhaForte#2026"})
                self.assertRedirects(resposta, reverse(destino), fetch_redirect_response=False)

    def test_conta_desactivada_nao_entra(self):
        self.estudante.estado_user = "desativado"
        self.estudante.save()
        resposta = self.client.post(reverse("login"), {"username": "estudante@ispb.ao", "senha": "SenhaForte#2026"})
        self.assertEqual(resposta.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_next_externo_e_ignorado(self):
        resposta = self.client.post(
            reverse("login") + "?next=https://malicioso.example/",
            {"username": "coord@ispb.ao", "senha": "SenhaForte#2026"},
        )
        self.assertRedirects(resposta, reverse("admink"), fetch_redirect_response=False)

    def test_cadastro_cria_estudante_desactivado(self):
        resposta = self.client.post(reverse("cadastro"), {
            "nome_completo": "Ana Maria Chivinda", "email": "ana@ispb.ao", "telefone": "923111222",
            "perfil": "estudante", "curso": self.curso.pk,
            "password1": "Tfc!Segura2026", "password2": "Tfc!Segura2026",
        })
        self.assertRedirects(resposta, reverse("login"), fetch_redirect_response=False)
        novo = Usuario.objects.get(email="ana@ispb.ao")
        self.assertEqual(novo.perfil, "estudante")
        self.assertEqual(novo.estado_user, "desativado")

    def test_cadastro_nao_permite_perfis_de_gestao(self):
        self.client.post(reverse("cadastro"), {
            "nome_completo": "Intruso Teste", "email": "intruso@ispb.ao", "telefone": "923111222",
            "perfil": "presidente", "curso": self.curso.pk,
            "password1": "Tfc!Segura2026", "password2": "Tfc!Segura2026",
        })
        self.assertFalse(Usuario.objects.filter(email="intruso@ispb.ao").exists())


class PermissoesTests(BaseTestCase):
    PAGINAS_GESTAO = [
        "admink", "dashboard_presidencia", "index_area_cientifica", "lista_estudantes", "lista_aprovados",
        "lista_reprovados", "lista_processos", "gerenciar_professores", "gerir_calendarios", "lista_actas",
        "listar_despachos", "criar_despacho", "lista_comunicados", "agendar_predefesa", "lista_solicitacoes",
        "fichas_por_curso_lista", "historico_aprovacoes", "lista_departamentos", "lista_cursos",
        "add_estudante", "inscricoes_aprovadas_coordenacao", "lista_cursos_predefesas", "area_cientifica_temas",
    ]

    def test_anonimo_e_enviado_para_login(self):
        for nome in self.PAGINAS_GESTAO + ["dashboard_estudante", "dashboard_tutor", "listar_notificacoes"]:
            with self.subTest(pagina=nome):
                resposta = self.client.get(reverse(nome))
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta["Location"].startswith(reverse("login")))

    def test_estudante_nao_acede_a_gestao(self):
        self.client.force_login(self.estudante)
        for nome in self.PAGINAS_GESTAO:
            with self.subTest(pagina=nome):
                self.assertEqual(self.client.get(reverse(nome)).status_code, 403)

    def test_estudante_so_baixa_as_suas_recomendacoes(self):
        self.client.force_login(self.estudante)
        url = reverse("baixar_recomendacoes", args=[self.outro_estudante.pk])
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_paginas_de_gestao_renderizam_para_coordenacao(self):
        self.client.force_login(self.coordenacao)
        for nome in self.PAGINAS_GESTAO:
            with self.subTest(pagina=nome):
                self.assertIn(self.client.get(reverse(nome)).status_code, (200, 302))

    def test_paineis_de_estudante_e_tutor_renderizam(self):
        casos = [
            (self.estudante, ["dashboard_estudante", "lista_inscricoes_tfc", "todas_recomendacoes",
                              "lista_geral_temas", "listar_notificacoes", "atualizar_perfil"]),
            (self.tutor, ["dashboard_tutor", "lista_estudantes_tutor", "listar_notificacoes"]),
        ]
        for user, paginas in casos:
            self.client.force_login(user)
            for nome in paginas:
                with self.subTest(user=user.perfil, pagina=nome):
                    self.assertEqual(self.client.get(reverse(nome)).status_code, 200)


class BackupTests(BaseTestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_user(
            email="admin@ispb.ao", password="SenhaForte#2026", nome="Admin", sobrenome="Sistema",
            telefone="923000001", perfil="cordenacao", estado_user="activo",
        )
        self.admin.is_superuser = True
        self.admin.save()

    def test_so_o_superadministrador_acede(self):
        for user in (self.coordenacao, self.presidente, self.estudante):
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse("backups")).status_code, 403)
            self.assertEqual(self.client.post(reverse("criar_backup")).status_code, 403)
        self.client.logout()
        self.assertEqual(self.client.get(reverse("backups")).status_code, 302)

    def test_pagina_e_download_do_zip(self):
        import io, json, zipfile
        from .models import RegistoBackup

        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("backups")), "Descarregar cópia agora")
        self.assertEqual(self.client.get(reverse("criar_backup")).status_code, 405)

        resposta = self.client.post(reverse("criar_backup"), {"incluir_media": "1"})
        self.assertEqual(resposta.status_code, 200)
        self.assertEqual(resposta["Content-Type"], "application/zip")
        self.assertIn("sgtf-backup-", resposta["Content-Disposition"])

        zf = zipfile.ZipFile(io.BytesIO(resposta.content))
        self.assertIn("dados.json", zf.namelist())
        self.assertIn("LEIAME.txt", zf.namelist())
        dados = json.loads(zf.read("dados.json"))
        emails = {o["fields"].get("email") for o in dados if o["model"] == "Coordenacao.usuario"}
        self.assertIn("estudante@ispb.ao", emails)
        registo = RegistoBackup.objects.get()
        self.assertEqual(registo.utilizador, self.admin)
        self.assertTrue(registo.incluiu_media)

    def test_copia_pode_ser_reposta(self):
        import io, json, os, tempfile, zipfile
        from django.core.management import call_command

        self.client.force_login(self.admin)
        zf = zipfile.ZipFile(io.BytesIO(self.client.post(reverse("criar_backup")).content))
        total = len(json.loads(zf.read("dados.json")))
        Usuario.objects.filter(email="outro@ispb.ao").delete()
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "dados.json")
            with open(caminho, "wb") as f:
                f.write(zf.read("dados.json"))
            call_command("loaddata", caminho, verbosity=0)
        self.assertTrue(Usuario.objects.filter(email="outro@ispb.ao").exists())
        self.assertGreater(total, 0)


class SugestoesTests(BaseTestCase):
    def setUp(self):
        from datetime import timedelta
        from django.utils import timezone
        from .models import ProcessoEtapa
        hoje = timezone.now().date()
        self.processo = ProcessoEtapa.objects.create(
            titulo="TFC 2026", curso=self.curso, coordenador=self.coordenacao,
            data_inicio=hoje - timedelta(days=1), data_termino=hoje + timedelta(days=30), ativo=True,
        )

    def _criar_sugestao(self, **extra):
        self.client.force_login(self.coordenacao)
        dados = {"titulo": "Gestão de stock da cantina", "descricao": "Controlar entradas e saídas.",
                 "curso": self.curso.pk, "tutor_sugerido": self.tutor.pk}
        dados.update(extra)
        self.client.post(reverse("gerir_sugestoes"), dados)
        from .models import TemaSugerido
        return TemaSugerido.objects.latest("criado_em")

    def test_permissoes(self):
        for user, url in [(self.estudante, "gerir_sugestoes"), (self.tutor, "gerir_sugestoes"),
                          (self.coordenacao, "sugestoes_estudante")]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(reverse(url)).status_code, 403)

    def test_coordenacao_cria_e_estudante_ve(self):
        s = self._criar_sugestao()
        self.assertEqual(s.criado_por, self.coordenacao)
        self.client.force_login(self.estudante)
        self.assertContains(self.client.get(reverse("sugestoes_estudante")), "Gestão de stock da cantina")

    def test_estudante_escolhe_e_tema_fica_reservado(self):
        from .models import NotificacaoFinal, Tema
        s = self._criar_sugestao()
        self.client.force_login(self.estudante)
        r = self.client.post(reverse("escolher_sugestao", args=[s.pk]), {"tutor_indicado": self.tutor.pk})
        self.assertRedirects(r, reverse("dashboard_estudante"), fetch_redirect_response=False)
        tema = Tema.objects.get(estudante=self.estudante)
        self.assertEqual(tema.titulo, s.titulo)
        self.assertEqual(tema.tutor_indicado, self.tutor)
        self.assertEqual(tema.processo, self.processo)
        s.refresh_from_db()
        self.assertTrue(s.escolhido)
        self.assertTrue(NotificacaoFinal.objects.filter(usuario=self.coordenacao, titulo="Tema sugerido escolhido").exists())

        self.client.force_login(self.outro_estudante)
        self.assertNotContains(self.client.get(reverse("sugestoes_estudante")), "Gestão de stock da cantina")
        self.client.post(reverse("escolher_sugestao", args=[s.pk]), {"tutor_indicado": self.tutor.pk})
        self.assertFalse(Tema.objects.filter(estudante=self.outro_estudante).exists())

        # coordenação rejeita: a sugestão volta a ficar disponível
        tema.status_coordenacao = "rejeitado"
        tema.save()
        s.refresh_from_db()
        self.assertTrue(s.disponivel)

    def test_sem_processo_aberto_nao_escolhe(self):
        from .models import Tema
        s = self._criar_sugestao()
        self.processo.ativo = False
        self.processo.save()
        self.client.force_login(self.estudante)
        self.client.post(reverse("escolher_sugestao", args=[s.pk]), {"tutor_indicado": self.tutor.pk})
        self.assertFalse(Tema.objects.filter(estudante=self.estudante).exists())

    def test_nao_elimina_tema_ja_escolhido(self):
        from .models import TemaSugerido
        s = self._criar_sugestao()
        self.client.force_login(self.estudante)
        self.client.post(reverse("escolher_sugestao", args=[s.pk]), {"tutor_indicado": self.tutor.pk})
        self.client.force_login(self.coordenacao)
        self.client.post(reverse("eliminar_sugestao", args=[s.pk]))
        self.assertTrue(TemaSugerido.objects.filter(pk=s.pk).exists())


class IATests(BaseTestCase):
    def setUp(self):
        import json
        from types import SimpleNamespace
        from datetime import timedelta
        from django.utils import timezone
        from .models import ProcessoEtapa, Tema
        self.json = json
        self.ns = SimpleNamespace
        hoje = timezone.now().date()
        ProcessoEtapa.objects.create(titulo="TFC 2026", curso=self.curso, coordenador=self.coordenacao,
                                     data_inicio=hoje - timedelta(days=1), data_termino=hoje + timedelta(days=30), ativo=True)
        self.tema_existente = Tema.objects.create(
            estudante=self.outro_estudante, titulo="Sistema de gestão de stock para a cantina universitária",
            descricao="Controlo de entradas e saídas de produtos da cantina com alertas de stock mínimo.",
            tutor_indicado=self.tutor,
        )

    def _cliente_falso(self, dados=None, stop_reason="end_turn"):
        from unittest import mock
        resposta = self.ns(stop_reason=stop_reason, content=[self.ns(type="text", text=self.json.dumps(dados or {}))])
        cliente = mock.MagicMock()
        cliente.beta.messages.create.return_value = resposta
        return mock.patch("Coordenacao.ia._cliente", return_value=cliente), cliente

    def _post(self, nome, dados, **kw):
        return self.client.post(reverse(nome, **kw), self.json.dumps(dados), content_type="application/json")

    def test_analise_encontra_tema_parecido_e_sugere_tutor(self):
        self.client.force_login(self.estudante)
        d = self._post("ia_analise", {"titulo": "Gestão de stock da cantina", "descricao": "Alertas de stock mínimo e controlo de produtos da cantina"}).json()
        self.assertTrue(d["semelhantes"])
        self.assertGreaterEqual(d["semelhantes"][0]["percentagem"], 50)
        self.assertEqual(d["tutores"][0]["id"], self.tutor.pk)

    def test_analise_nao_compara_com_o_proprio_estudante(self):
        self.client.force_login(self.outro_estudante)
        d = self._post("ia_analise", {"titulo": "Sistema de gestão de stock para a cantina universitária", "descricao": ""}).json()
        self.assertEqual(d["semelhantes"], [])

    def test_proposta_sem_chave(self):
        self.client.force_login(self.estudante)
        with self.settings(ANTHROPIC_API_KEY=""):
            r = self._post("ia_proposta", {"ideia": "Uma aplicação para marcar atendimento na secretaria."})
        self.assertEqual(r.status_code, 503)

    def test_proposta_com_ia(self):
        dados = {
            "titulo": "Aplicação de marcação de atendimento na secretaria do ISP-Bié",
            "problema": "Os estudantes perdem horas em filas.", "objetivo_geral": "Desenvolver uma aplicação de marcação.",
            "objetivos_especificos": ["Levantar requisitos", "Implementar", "Avaliar"],
            "metodologia": "Desenvolvimento iterativo com testes de usabilidade.", "palavras_chave": ["marcação", "filas"],
        }
        patch, cliente = self._cliente_falso(dados)
        self.client.force_login(self.estudante)
        with self.settings(ANTHROPIC_API_KEY="teste"), patch:
            d = self._post("ia_proposta", {"ideia": "Uma aplicação para marcar atendimento na secretaria."}).json()
        self.assertTrue(d["ok"])
        self.assertEqual(d["titulo"], dados["titulo"])
        self.assertIn("Objetivos específicos", d["descricao"])
        self.assertLessEqual(len(d["descricao"].split()), 250)
        kwargs = cliente.beta.messages.create.call_args.kwargs
        self.assertEqual(kwargs["output_config"]["format"]["type"], "json_schema")
        self.assertEqual(kwargs["fallbacks"], "default")

    def test_proposta_recusada(self):
        patch, _ = self._cliente_falso(stop_reason="refusal")
        self.client.force_login(self.estudante)
        with self.settings(ANTHROPIC_API_KEY="teste"), patch:
            r = self._post("ia_proposta", {"ideia": "Uma ideia qualquer para o meu trabalho de fim de curso."})
        self.assertEqual(r.status_code, 400)
        self.assertFalse(r.json()["ok"])

    def test_limite_por_hora(self):
        from django.core.cache import cache
        cache.clear()
        dados = {"titulo": "T", "problema": "P", "objetivo_geral": "O", "objetivos_especificos": ["a"], "metodologia": "M", "palavras_chave": []}
        patch, _ = self._cliente_falso(dados)
        self.client.force_login(self.estudante)
        with self.settings(ANTHROPIC_API_KEY="teste", IA_LIMITE_POR_HORA=1), patch:
            self.assertEqual(self._post("ia_proposta", {"ideia": "Primeira ideia com detalhe suficiente."}).status_code, 200)
            self.assertEqual(self._post("ia_proposta", {"ideia": "Segunda ideia com detalhe suficiente."}).status_code, 429)
        cache.clear()

    def _predefesa(self):
        from datetime import date, time
        from .models import Predefesa, Usuario
        juri = [Usuario.objects.create_user(email=f"j{i}@ispb.ao", password="x", nome="Juri", sobrenome=str(i),
                                            telefone="923000000", perfil="tutor", estado_user="activo") for i in range(4)]
        Predefesa.objects.bulk_create([Predefesa(
            data=date(2026, 12, 1), hora=time(10, 0), estudante=self.outro_estudante, tema=self.tema_existente,
            presidente=juri[0], secretario=juri[1], primeiro_vogal=juri[2], segundo_vogal=juri[3],
        )])
        return juri

    def test_resumo_juri_permissoes_e_geracao(self):
        from .models import ResumoIA
        juri = self._predefesa()
        url = reverse("resumo_juri", args=[self.tema_existente.pk])
        for user, esperado in [(self.estudante, 403), (self.coordenacao, 200), (juri[2], 200), (self.tutor, 200)]:
            self.client.force_login(user)
            self.assertEqual(self.client.get(url).status_code, esperado, user.email)

        conteudo = {"sintese": "S", "objetivos": ["o"], "metodologia": "m", "contributos": ["c"],
                    "pontos_de_atencao": ["p"], "perguntas_sugeridas": ["q?"]}
        patch, _ = self._cliente_falso(conteudo)
        self.client.force_login(self.coordenacao)
        with self.settings(ANTHROPIC_API_KEY="teste"), patch:
            self.client.post(url)
        r = ResumoIA.objects.get(tema=self.tema_existente)
        self.assertEqual(r.conteudo["fonte"], "descricao")
        self.client.force_login(juri[0])
        self.assertContains(self.client.get(url), "Perguntas sugeridas")

    def test_minhas_bancas(self):
        juri = self._predefesa()
        self.client.force_login(juri[1])
        r = self.client.get(reverse("minhas_bancas"))
        self.assertContains(r, "Secretário")
        self.assertContains(r, self.tema_existente.titulo)


class ProgressoTests(BaseTestCase):
    def setUp(self):
        import tempfile
        from datetime import timedelta
        from django.utils import timezone
        from .models import ProcessoEtapa, Tema
        self.td = timedelta
        self.hoje = timezone.localdate()
        ProcessoEtapa.objects.create(titulo="TFC 2026", curso=self.curso, coordenador=self.coordenacao,
                                     data_inicio=self.hoje - timedelta(days=1), data_termino=self.hoje + timedelta(days=30), ativo=True)
        self.tema = Tema.objects.create(estudante=self.estudante, titulo="Gestão de stock", descricao="x",
                                        tutor_indicado=self.tutor, status_tutor="aprovado", status_coordenacao="aprovado")
        self.media = self.settings(MEDIA_ROOT=tempfile.mkdtemp())
        self.media.enable()

    def tearDown(self):
        self.media.disable()

    def _plano(self):
        self.client.force_login(self.tutor)
        prazo = (self.hoje + self.td(days=100)).isoformat()
        self.client.post(reverse("criar_plano", args=[self.tema.pk]), {"prazo_final": prazo})
        self.client.logout()
        return self.tema.plano

    def test_tutor_cria_plano_padrao_com_prazos_crescentes(self):
        plano = self._plano()
        prazos = list(plano.etapas.values_list("prazo", flat=True))
        self.assertEqual(len(prazos), 5)
        self.assertEqual(prazos, sorted(prazos))
        self.assertEqual(prazos[-1], self.hoje + self.td(days=100))

    def test_outro_tutor_nao_altera_etapas(self):
        outro = Usuario.objects.create_user(email="t2@ispb.ao", password="SenhaForte#2026", nome="T", sobrenome="2",
                                            telefone="923000001", perfil="tutor", estado_user="activo")
        self.client.force_login(outro)
        r = self.client.post(reverse("criar_plano", args=[self.tema.pk]), {"prazo_final": "2099-01-01"})
        self.assertEqual(r.status_code, 403)

    def test_coordenacao_ve_mas_nao_edita(self):
        self._plano()
        self.client.force_login(self.coordenacao)
        self.assertContains(self.client.get(reverse("progresso_geral")), "Gestão de stock")
        r = self.client.get(reverse("progresso_tema", args=[self.tema.pk]))
        self.assertEqual(r.status_code, 200)
        self.assertNotContains(r, "Adicionar etapa")
        self.assertEqual(self.client.post(reverse("nova_etapa", args=[self.tema.pk]), {"titulo": "x", "prazo": "2099-01-01"}).status_code, 403)

    def test_entrega_e_aprovacao_atualizam_progresso(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        from .progresso import resumo
        plano = self._plano()
        etapa = plano.etapas.first()

        self.client.force_login(self.estudante)
        self.assertContains(self.client.get(reverse("meu_progresso")), "Introdução")
        self.client.post(reverse("entregar_etapa", args=[etapa.pk]),
                         {"ficheiro": SimpleUploadedFile("intro.pdf", b"%PDF-1.4"), "comentario": "Primeira versão"})
        etapa.refresh_from_db()
        self.assertEqual(etapa.estado, "entregue")

        self.client.force_login(self.tutor)
        self.client.post(reverse("avaliar_etapa", args=[self.tema.pk, etapa.pk]), {"decisao": "aprovada"})
        self.assertEqual(resumo(plano)["percentagem"], 20)

    def test_estudante_nao_entrega_etapa_de_outro(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        etapa = self._plano().etapas.first()
        self.client.force_login(self.outro_estudante)
        r = self.client.post(reverse("entregar_etapa", args=[etapa.pk]), {"ficheiro": SimpleUploadedFile("a.pdf", b"x")})
        self.assertEqual(r.status_code, 404)

    def test_alertas_nao_se_repetem(self):
        from .models import EtapaTrabalho, NotificacaoFinal, PlanoTrabalho
        from .progresso import gerar_alertas
        plano = PlanoTrabalho.objects.create(tema=self.tema)
        EtapaTrabalho.objects.create(plano=plano, ordem=1, titulo="Introdução", prazo=self.hoje + self.td(days=2))
        EtapaTrabalho.objects.create(plano=plano, ordem=2, titulo="Metodologia", prazo=self.hoje - self.td(days=1))

        c = gerar_alertas()
        self.assertEqual((c["prazo"], c["atraso"]), (1, 1))
        self.assertEqual(gerar_alertas(), {"prazo": 0, "atraso": 0, "parado": 0})
        alertas = NotificacaoFinal.objects.filter(titulo__in=["Prazo a terminar", "Etapa em atraso", "Orientando com etapa em atraso"])
        self.assertEqual(alertas.filter(usuario=self.estudante).count(), 2)
        self.assertEqual(alertas.filter(usuario=self.tutor).count(), 1)

    def test_estudante_parado_avisa_tutor_e_coordenacao(self):
        from .models import EtapaTrabalho, NotificacaoFinal, PlanoTrabalho
        from .progresso import gerar_alertas
        plano = PlanoTrabalho.objects.create(tema=self.tema)
        PlanoTrabalho.objects.filter(pk=plano.pk).update(criado_em=plano.criado_em - self.td(days=40))
        EtapaTrabalho.objects.create(plano=plano, ordem=1, titulo="Introdução", prazo=self.hoje + self.td(days=20))

        self.assertEqual(gerar_alertas()["parado"], 1)
        self.assertTrue(NotificacaoFinal.objects.filter(usuario=self.coordenacao, titulo="Estudante parado").exists())
        self.assertTrue(NotificacaoFinal.objects.filter(usuario=self.tutor, titulo="Estudante parado").exists())
        self.assertEqual(gerar_alertas()["parado"], 0)
