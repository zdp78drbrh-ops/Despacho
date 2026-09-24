import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True
    dependencies = [migrations.swappable_dependency(settings.AUTH_USER_MODEL)]

    operations = [
        migrations.CreateModel(
            name="EventoAuditoria",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fecha", models.DateTimeField(blank=True, db_index=True, null=True)),
                ("usuario_nombre", models.CharField(blank=True, default="", max_length=120)),
                ("ip", models.GenericIPAddressField(blank=True, null=True)),
                ("accion", models.CharField(db_index=True, max_length=40)),
                ("entidad", models.CharField(db_index=True, max_length=40)),
                ("entidad_id", models.CharField(blank=True, db_index=True, default="", max_length=40)),
                ("descripcion", models.TextField(blank=True, default="")),
                ("datos", models.JSONField(blank=True, default=dict)),
                ("hash_anterior", models.CharField(blank=True, default="", max_length=64)),
                ("hash", models.CharField(blank=True, default="", max_length=64)),
                ("usuario", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                              related_name="+", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-id"], "verbose_name": "evento de auditoría",
                     "verbose_name_plural": "eventos de auditoría"},
        ),
    ]
