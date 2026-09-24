-- Endurecimiento opcional (recomendado en producción): la aplicación usa un rol que NO es dueño de las
-- tablas de auditoría, así que ni siquiera puede desactivar los triggers. Ejecutar como administrador del
-- clúster DESPUÉS de correr las migraciones con el rol dueño (despacho_owner).
--
--   psql "$DATABASE_URL_ADMIN" -v app=despacho_app -f ops/sql/roles.sql

GRANT CONNECT ON DATABASE despacho TO :app;
GRANT USAGE ON SCHEMA public TO :app;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO :app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO :app;
-- Solo alta: sin UPDATE/DELETE/TRUNCATE (además de los triggers)
REVOKE UPDATE, DELETE, TRUNCATE ON auditoria_eventoauditoria, litigios_entradabitacora, litigios_acuerdo FROM :app;
-- Nada se borra físicamente en las tablas del dominio
REVOKE DELETE, TRUNCATE ON ALL TABLES IN SCHEMA public FROM :app;
-- Excepción: sesiones de Django (se limpian con clearsessions)
GRANT DELETE ON django_session TO :app;
