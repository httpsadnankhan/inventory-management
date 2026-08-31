from django.db import migrations, models


def deduplicate_product_names(apps, schema_editor):
    Product = apps.get_model("inventory", "Product")
    seen = {}

    for product in Product.objects.order_by("id"):
        base_name = (product.name or "").strip()
        if not base_name:
            continue

        key = base_name.lower()
        count = seen.get(key, 0) + 1
        seen[key] = count

        if count > 1:
            product.name = f"{base_name} ({count})"
            product.save(update_fields=["name"])


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_remove_product_low_stock_threshold"),
    ]

    operations = [
        migrations.RunPython(deduplicate_product_names, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="product",
            name="name",
            field=models.CharField(max_length=200, unique=True),
        ),
    ]
