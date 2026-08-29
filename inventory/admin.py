from django.contrib import admin
from .models import Category, Product, Sale, RepairRecord, ShopSettings


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "metal_type", "weight", "quantity", "buy_price", "sale_price", "created_at")
    list_filter = ("category", "metal_type")
    search_fields = ("name", "sku")
    readonly_fields = ("sku", "created_at", "updated_at")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "unit_price", "discount", "total_amount", "customer_name", "sold_by", "sale_date")
    list_filter = ("sale_date",)
    search_fields = ("customer_name", "product__name")
    readonly_fields = ("total_amount", "sale_date", "updated_at")


@admin.register(RepairRecord)
class RepairRecordAdmin(admin.ModelAdmin):
    list_display = ("product", "quantity", "sent_to", "sent_date", "expected_return_date", "received_date", "status")
    list_filter = ("status",)
    search_fields = ("product__name", "sent_to")


@admin.register(ShopSettings)
class ShopSettingsAdmin(admin.ModelAdmin):
    list_display = ("shop_name", "phone", "email", "updated_at")

    def has_add_permission(self, request):
        # Singleton — only one row should ever exist.
        return not ShopSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False
