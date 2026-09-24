# Operación del sistema

## 1. Correr en local (desarrollo)

Requisitos: Python 3.12 y PostgreSQL 16 (o Docker).

```bash
pip install -r requirements-dev.txt
cp .env.example .env            # y ajusta DATABASE_URL; exporta las variables (p. ej. con `set -a; . ./.env`)
python manage.py migrate
python manage.py cargar_ejemplo # opcional: datos de ejemplo del prototipo (contraseña: despacho-demo-2026)
python manage.py runserver      # http://localhost:8000
```

Con Docker: `docker compose up` y en otra terminal `docker compose exec web python manage.py cargar_ejemplo`.

Pruebas: `pytest` · Estilo: `ruff check . && ruff format --check .`

## 2. Puesta en producción (una sola vez)

1. **DigitalOcean**
   - Crear el clúster de PostgreSQL 16 administrado `despacho-db` (Basic, 1 GB, región SFO3).
   - Crear dos Spaces privados en SFO3: `despacho-pdf`. Activar *versionado* del bucket. Generar una llave de acceso de Spaces.
   - Crear la App con `.do/app.yaml` (Apps → Create → *App spec*), conectando el repositorio de GitHub.
   - Llenar las variables marcadas `CAMBIAR` (tipo *Encrypted*). `DJANGO_SECRET_KEY`: una cadena aleatoria de 50+ caracteres.
2. **Dominio**: en el registrador, crear `sistema` (CNAME) apuntando al dominio que da DigitalOcean; agregarlo en App → Settings → Domains. El certificado HTTPS es automático.
3. **Resend**: verificar el dominio (registros SPF/DKIM que indica Resend), crear una API key y ponerla en `EMAIL_HOST_PASSWORD`.
4. **Backblaze B2**: crear el bucket privado `despacho-respaldos` con *Object Lock* o al menos *lifecycle* que conserve versiones; crear una *application key* limitada a ese bucket y ponerla en `RESPALDO_ACCESS_KEY` / `RESPALDO_SECRET_KEY`. Ajustar `RESPALDO_ENDPOINT_URL` a la región del bucket.
5. **Primer administrador**: en la consola de la App (componente `web` → Console):
   `python manage.py createsuperuser` (correo, nombre, contraseña). Entrar y dar de alta al equipo en Configuración; cada persona recibe un correo para definir su contraseña.
6. (Opcional, recomendado) Endurecer permisos de la base con `ops/sql/roles.sql` (ver comentarios del archivo).
7. Si hay datos capturados en el prototipo: en el prototipo, Configuración → Exportar respaldo, guardar el texto como `respaldo.json` y correr
   `python manage.py importar_prototipo respaldo.json --simular` y, si el resumen es correcto, sin `--simular`.
   Después corregir en Configuración el correo de los usuarios creados como `@importado.invalid` y enviarles acceso.

## 3. Tareas automáticas (componente `programador`)

| Hora (CDMX) | Tarea | Qué hace |
|---|---|---|
| 02:00 | `respaldar` | Verifica la cadena de auditoría (avisa por correo si está rota), `pg_dump` a B2, ancla del último hash, réplica de PDF nuevos, depura respaldos (30 diarios + 12 mensuales). |
| 03:00 | `clearsessions` | Limpia sesiones vencidas. |

Además, DigitalOcean hace respaldo diario de la base con recuperación a un punto en el tiempo (7 días).

## 4. Prueba de restauración (mensual, obligatoria)

1. Descargar de B2 el respaldo más reciente `bd/AAAA/MM/despacho-….dump`.
2. En una base vacía (local o un clúster de prueba): `createdb restaurada && pg_restore --no-owner -d restaurada despacho-….dump`
3. Verificar: `psql -d restaurada -c "select count(*), auditoria_verificar() is null as integra from auditoria_eventoauditoria"` → `integra = t`.
4. Comparar el último `id hash` con el archivo `anclas/…` del mismo día en B2: deben coincidir.
5. Anotar fecha y resultado en la tabla de abajo y borrar la base de prueba.

| Fecha | Respaldo | Íntegra | Ancla coincide | Quién |
|---|---|---|---|---|
| | | | | |

## 5. Si algo sale mal

- **Alguien borró o cambió algo por error**: nada se borra físicamente. Buscar en Configuración → Bitácora de auditoría el evento (tiene el antes y el después) y corregir desde la pantalla; si fue una baja, un administrador puede reactivar el registro desde `/admin/`.
- **Alerta "cadena de auditoría rota"**: no tocar la base. Avisar al responsable técnico; comparar con las anclas en B2 para ubicar desde cuándo.
- **Restaurar producción a un momento anterior**: DigitalOcean → Databases → despacho-db → Backups → *Restore to point in time* (crea un clúster nuevo; luego cambiar `DATABASE_URL`).
