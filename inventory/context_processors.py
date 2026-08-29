"""
Context processors for inventory app.
Makes frequently used data available to all templates.
"""
from .models import ShopSettings


def shop(request):
    """Make shop settings available in all templates as 'shop' variable."""
    return {"shop": ShopSettings.load()}
