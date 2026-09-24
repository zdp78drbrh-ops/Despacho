"""La bitácora visible de los expedientes y los acuerdos publicados son de solo alta, igual que la auditoría."""
from django.db import migrations

TABLAS = ["litigios_entradabitacora", "litigios_acuerdo"]

SQL = "".join(f"""
CREATE TRIGGER inmutable BEFORE UPDATE OR DELETE ON {t} FOR EACH ROW EXECUTE FUNCTION auditoria_inmutable();
CREATE TRIGGER inmutable_truncate BEFORE TRUNCATE ON {t} FOR EACH STATEMENT EXECUTE FUNCTION auditoria_inmutable();
""" for t in TABLAS)
REVERSO = "".join(f"DROP TRIGGER IF EXISTS inmutable ON {t}; DROP TRIGGER IF EXISTS inmutable_truncate ON {t};"
                  for t in TABLAS)


class Migration(migrations.Migration):
    dependencies = [("litigios", "0001_initial"), ("auditoria", "0002_inmutable")]
    operations = [migrations.RunSQL(SQL, REVERSO)]
