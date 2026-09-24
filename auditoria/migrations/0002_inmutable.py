"""Hace inmutable la bitácora de auditoría a nivel base de datos.

- auditoria_sellar(): antes de insertar toma un candado, asigna id y fecha (la aplicación no puede
  antedatar), y calcula hash = sha256(hash_anterior | contenido).
- auditoria_inmutable(): rechaza UPDATE, DELETE y TRUNCATE.
- auditoria_verificar(): recorre la cadena y devuelve el primer id alterado (NULL si está íntegra).
"""
from django.db import migrations

T = "auditoria_eventoauditoria"

SQL = f"""
CREATE OR REPLACE FUNCTION auditoria_hash(prev text, id bigint, fecha timestamptz, usuario_id bigint,
    usuario_nombre text, ip inet, accion text, entidad text, entidad_id text, descripcion text, datos jsonb)
RETURNS text LANGUAGE sql IMMUTABLE AS $$
  SELECT encode(sha256(convert_to(
    coalesce(prev,'') || '|' || id::text || '|' ||
    to_char(fecha AT TIME ZONE 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US') || '|' ||
    coalesce(usuario_id::text,'') || '|' || coalesce(usuario_nombre,'') || '|' || coalesce(host(ip),'') || '|' ||
    coalesce(accion,'') || '|' || coalesce(entidad,'') || '|' || coalesce(entidad_id,'') || '|' ||
    coalesce(descripcion,'') || '|' || coalesce(datos::text,'null'), 'UTF8')), 'hex')
$$;

CREATE OR REPLACE FUNCTION auditoria_sellar() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE prev text;
BEGIN
  PERFORM pg_advisory_xact_lock(72430001);
  NEW.id := nextval(pg_get_serial_sequence('{T}', 'id'));
  NEW.fecha := clock_timestamp();
  SELECT hash INTO prev FROM {T} ORDER BY id DESC LIMIT 1;
  NEW.hash_anterior := coalesce(prev, '');
  NEW.hash := auditoria_hash(NEW.hash_anterior, NEW.id, NEW.fecha, NEW.usuario_id, NEW.usuario_nombre,
                             NEW.ip, NEW.accion, NEW.entidad, NEW.entidad_id, NEW.descripcion, NEW.datos);
  RETURN NEW;
END $$;

CREATE OR REPLACE FUNCTION auditoria_inmutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'El registro % es de solo alta: no se puede modificar ni borrar', TG_TABLE_NAME
    USING ERRCODE = 'insufficient_privilege';
END $$;

CREATE OR REPLACE FUNCTION auditoria_verificar() RETURNS bigint LANGUAGE plpgsql STABLE AS $$
DECLARE r record; prev text := '';
BEGIN
  FOR r IN SELECT * FROM {T} ORDER BY id LOOP
    IF r.hash_anterior <> prev OR r.hash <> auditoria_hash(r.hash_anterior, r.id, r.fecha, r.usuario_id,
        r.usuario_nombre, r.ip, r.accion, r.entidad, r.entidad_id, r.descripcion, r.datos) THEN
      RETURN r.id;
    END IF;
    prev := r.hash;
  END LOOP;
  RETURN NULL;
END $$;

CREATE TRIGGER sellar BEFORE INSERT ON {T} FOR EACH ROW EXECUTE FUNCTION auditoria_sellar();
CREATE TRIGGER inmutable BEFORE UPDATE OR DELETE ON {T} FOR EACH ROW EXECUTE FUNCTION auditoria_inmutable();
CREATE TRIGGER inmutable_truncate BEFORE TRUNCATE ON {T} FOR EACH STATEMENT EXECUTE FUNCTION auditoria_inmutable();
"""

REVERSO = f"""
DROP TRIGGER IF EXISTS sellar ON {T};
DROP TRIGGER IF EXISTS inmutable ON {T};
DROP TRIGGER IF EXISTS inmutable_truncate ON {T};
DROP FUNCTION IF EXISTS auditoria_verificar();
DROP FUNCTION IF EXISTS auditoria_sellar();
"""


class Migration(migrations.Migration):
    dependencies = [("auditoria", "0001_initial")]
    operations = [migrations.RunSQL(SQL, REVERSO)]
