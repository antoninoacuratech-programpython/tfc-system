from django.apps import AppConfig

class CoordenacaoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'Coordenacao'

    def ready(self):
        # Isso faz o Django registrar os gatilhos no momento que o servidor sobe
        import Coordenacao.signals