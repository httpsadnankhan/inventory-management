from django.test import TestCase

from .models import Product, Category


class ProductStockStatusTests(TestCase):
    def test_zero_quantity_is_out_of_stock(self):
        category = Category.objects.create(name="Rings")
        product = Product.objects.create(
            name="Gold Ring",
            sku="RING-001",
            category=category,
            quantity=0,
            buy_price=100,
            sale_price=150,
        )

        self.assertFalse(product.is_in_stock)
        self.assertTrue(product.is_out_of_stock)

    def test_positive_quantity_is_in_stock(self):
        category = Category.objects.create(name="Rings")
        product = Product.objects.create(
            name="Gold Ring",
            sku="RING-002",
            category=category,
            quantity=5,
            buy_price=100,
            sale_price=150,
        )

        self.assertTrue(product.is_in_stock)
        self.assertFalse(product.is_out_of_stock)
