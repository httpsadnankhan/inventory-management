from django.db.models.signals import pre_delete, pre_save
from django.dispatch import receiver
from django.core.files.storage import default_storage
from .models import Product, ShopSettings


@receiver(pre_delete, sender=Product)
def delete_product_image(sender, instance, **kwargs):
    """Delete product image file when product is deleted"""
    if instance.image:
        # Get the image path
        image_path = instance.image.name
        # Delete the file if it exists
        if default_storage.exists(image_path):
            default_storage.delete(image_path)


@receiver(pre_save, sender=ShopSettings)
def delete_old_logo(sender, instance, **kwargs):
    """Delete old logo file when a new logo is uploaded"""
    if not instance.pk:
        # New instance, no old logo to delete
        return
    
    try:
        # Get the existing instance from database
        old_instance = ShopSettings.objects.get(pk=instance.pk)
    except ShopSettings.DoesNotExist:
        # Instance doesn't exist in database yet
        return
    
    # Check if logo has changed
    old_logo = old_instance.logo
    new_logo = instance.logo
    
    # If logo exists and is different from the old one, delete the old one
    if old_logo and old_logo != new_logo:
        # Get the old logo path
        old_logo_path = old_logo.name
        # Delete the file if it exists
        if default_storage.exists(old_logo_path):
            default_storage.delete(old_logo_path)
