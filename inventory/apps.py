from django.apps import AppConfig


class InventoryConfig(AppConfig):
    name = 'inventory'
    
    def ready(self):
        """Import signals when the app is ready"""
        import inventory.signals
