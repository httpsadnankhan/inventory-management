from django.test import TestCase

from .forms import ProductForm
from .models import Product, Category, ShopSettings


class ProductSkuGenerationTests(TestCase):
    def setUp(self):
        self.category = Category.objects.create(name="Rings")
        self.shop = ShopSettings.load()
        self.shop.shop_name = "My Shop"
        self.shop.save()

    def test_sku_number_uses_active_product_count_after_delete(self):
        Product.objects.create(
            name="Gold Ring",
            category=self.category,
            quantity=1,
            buy_price=100,
            sale_price=150,
        )
        Product.objects.create(
            name="Silver Ring",
            category=self.category,
            quantity=1,
            buy_price=120,
            sale_price=180,
        )

        Product.objects.filter(name="Silver Ring").delete()

        product = Product.objects.create(
            name="Diamond Ring",
            category=self.category,
            quantity=1,
            buy_price=200,
            sale_price=260,
        )

        self.assertEqual(product.sku, "MYS-0002")

    def test_two_word_shop_name_uses_custom_prefix(self):
        self.shop.shop_name = "Royal Gold"
        self.shop.save()

        product = Product.objects.create(
            name="Gold Ring",
            category=self.category,
            quantity=1,
            buy_price=100,
            sale_price=150,
        )

        self.assertEqual(product.sku.startswith("ROG-"), True)

    def test_three_word_shop_name_uses_first_letter_of_each_word(self):
        self.shop.shop_name = "Gold Jewel Palace"
        self.shop.save()

        product = Product.objects.create(
            name="Gold Ring",
            category=self.category,
            quantity=1,
            buy_price=100,
            sale_price=150,
        )

        self.assertEqual(product.sku.startswith("GJP-"), True)


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

    def test_duplicate_product_name_is_invalid(self):
        category = Category.objects.create(name="Rings")
        Product.objects.create(
            name="Gold Ring",
            sku="RING-001",
            category=category,
            quantity=2,
            buy_price=100,
            sale_price=150,
        )

        form = ProductForm(
            data={
                "name": "Gold Ring",
                "category": category.id,
                "metal_type": "GOLD",
                "weight": 5,
                "weight_unit": "GRAM",
                "quantity": 1,
                "buy_price": 90,
                "sale_price": 160,
                "description": "Duplicate test",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("name", form.errors)
        self.assertIn("already exists", form.errors["name"][0])
