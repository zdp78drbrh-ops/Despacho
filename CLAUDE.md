# Despacho · Sistema de gestión jurídica

Guía permanente del proyecto. **Léela completa al inicio de cada sesión** y actualiza la sección
"Estado actual" al terminar cada bloque de trabajo.

## 1. Qué estamos construyendo

La versión de producción del prototipo `Despacho · Gestión jurídica` (un solo HTML con localStorage)
para un despacho jurídico en Querétaro, México. El prototipo es la **especificación funcional**:
pantallas, flujos, textos y reglas se conservan tal cual. Lo que cambia es la base técnica:

- Usuarios reales con contraseña y roles (sustituye el selector "Estoy trabajando como").
- Base de datos compartida en servidor (sustituye localStorage / `window.claude.use('db')`).
- Archivos PDF reales por expediente y por cliente (el prototipo solo registra nombre y fecha).
- Bitácora de auditoría inmutable.
- Correo automático cuando un plazo entra en rojo.
- Calendario de días inhábiles configurable para el cómputo de plazos.
- Respaldos automáticos.

### Documentos de referencia (fuente de verdad)

- `docs/referencia/prototipo.html` — prototipo funcional. **Si hay duda sobre una regla, manda el prototipo.**
  ⚠️ El archivo subido en la sesión 2 es una versión **anterior** a la que se pegó en el chat de la sesión 1:
  no trae "Apelaciones y amparos" (`RECURSOS`, `recCard`, `VIEWS.recursos`, expedientes e9/e10). El sistema
  implementa la versión **con** apelaciones y amparos (la pegada), porque así lo piden los requisitos. Si se
  consigue ese archivo, reemplazar `docs/referencia/prototipo.html` con él.
- El manual de operación y el bosquejo se omitieron por decisión del despacho (sesión 2).

## 2. Reglas del prototipo que no se pueden romper

Toda regla de esta lista debe tener una prueba automatizada que la cubra.

### Acciones del expediente (flujo con revisión y aprobación)
- Estados: `pendiente → elaboracion → revision → aprobada → terminada`
  (etiquetas: Pendiente, En elaboración, En revisión, Aprobada, Terminada).
- Botones según el siguiente estado: "Iniciar", "A revisión", "Aprobar", "Terminar".
- Solo se puede **terminar** una acción `aprobada`, o una sin revisor **ni** aprobador que no esté `pendiente`.
- Al pasar a revisión se anota "A revisión: {título}" en la bitácora; al aprobar, "Aprobado: {título}".
- Terminar pide acuse/folio, fecha de realización y (casilla) registrarla como documento del expediente
  (marcada por defecto si el tipo es Promoción o Escrito). Anota "{título} · {acuse}" en la bitácora.
- Tipos: Promoción, Escrito, Acto procesal, Diligencia, Gestión, Audiencia.
- Una acción puede pertenecer a un recurso (apelación/amparo) o al expediente principal.

### "Esperando auto"
- Al terminar una acción de tipo **Promoción** o **Escrito**, el expediente queda `esperandoAuto = true`.
- Al registrar un acuerdo publicado de ese expediente, `esperandoAuto = false`, se anota
  "Se registró acuerdo: {síntesis}" y, si se pidió y la acción no es "Solo registrar", se crea una acción
  pendiente de tipo Promoción con el plazo del acuerdo y la nota "Derivada del acuerdo del {fecha}".
- En el tablero, los expedientes esperando auto aparecen con chip gris "Esperando auto".

### Semáforo (días naturales, como en el prototipo)
- Plazo de acción: vencido / hoy / mañana / ≤ 3 días → **rojo**; ≤ 7 días → **ámbar**; resto → azul.
- Sin actuación (días desde la última entrada de bitácora): > 60 → **rojo**; > 30 → **ámbar**.
- Urgencia del expediente, en este orden: plazo ≤ 3 rojo; > 60 días sin actuación rojo; plazo ≤ 7 ámbar;
  > 30 días sin actuación ámbar. Orden del tablero por `orden` (días al plazo; −1 para sin impulso rojo; 50 para ámbar).
- Fechas corporativas (`chipFecha`): vencido o ≤ 7 rojo; ≤ 30 ámbar; resto azul.
- Estados de expediente: `activo`, `sentencia` (En espera de sentencia), `terminado`.
  Cambiar la etapa a "Citado a sentencia" pasa el estado a `sentencia`.

### Apelaciones y amparos
- Tipos y etapas exactamente como el catálogo `RECURSOS` del prototipo (Apelación, Amparo directo,
  Amparo indirecto, Recurso de revisión (amparo), Queja, Revocación o reposición), con su órgano por defecto.
- Promovente: Nosotros / Contraparte (chip azul "Lo promovimos" / ámbar "De la contraparte").
- Avanzar / Regresar etapa (avanzar anota en bitácora), Resolver (resultado, fecha, síntesis, etapa
  posterior del expediente; marca las acciones pendientes del recurso con "Recurso resuelto, revisar si
  sigue pendiente"), Reabrir.
- Suspensión solo se muestra en amparo indirecto; chips verde (concedida), rojo (negada), gris (otro).
- Al registrar un recurso: la etapa del expediente pasa a "Amparo" o "Apelación" y un expediente en
  `sentencia` vuelve a `activo`.

### Servicios corporativos y trámites (fases 3 y 4)
- Contratos por celebrar: `elaboracion → revision → aprobacion → aprobado → firmado`; al firmar pasan
  a contratos celebrados. Carpetas de documentos del cliente: las 7 de `CARPETAS`.
- Poderes, cumplimiento corporativo, contingencias (convertibles en expediente), due diligence semestral.
- Trámites: etapas `documentacion → ingreso → prevencion → resolucion → entrega → concluido`,
  lista de documentos precargada por tipo (`TIPOS_TRAM`), documento que "Bloquea", coadyuvantes,
  aviso al avanzar desde documentación si faltan documentos.

### Otros
- "Informe al cliente": texto generado listo para copiar (expediente, cliente, trámite) — mismo texto que el prototipo.
- Catálogos (`MATERIAS`, `ETAPAS`, `TIPOS_ACCION`, `RECURSOS`, `SUSPENSION`, `RESULTADOS`, …) se copian literalmente.
- Formato de fechas: "24 sep" (año solo si no es el actual), largo "jueves 24 de septiembre de 2026".
  Moneda `es-MX`. Zona horaria `America/Mexico_City`.

## 3. Arquitectura

```
Navegador (HTML del servidor + CSS del prototipo + static/js/despacho.js)
        │ HTTPS
        ▼
Aplicación Django (Python 3.12) ──► PostgreSQL 16 (datos + bitácora de auditoría)
   │   │                           
   │   └─► Almacenamiento de objetos S3 privado (PDF)   
   │                                                     
   └─ Proceso `programador` (worker aparte, manage.py programador):
        · 02:00 verificación de la cadena de auditoría + respaldo BD + réplica de PDF → Backblaze B2
        · 03:00 limpieza de sesiones
        · 07:00 revisar plazos → correo (fase 2)
```

### Decisiones técnicas y por qué

| Pieza | Elección | Motivo |
|---|---|---|
| Backend | **Django 5** (Python) | Autenticación, contraseñas (Argon2), grupos/permisos, formularios, migraciones, admin e i18n en español listos. Menos código propio que mantener. |
| Interfaz | **Plantillas Django + ~100 líneas de JS propio** (`static/js/despacho.js`), CSS del prototipo copiado tal cual | Conserva las pantallas exactamente; no hace falta una SPA ni dependencias JS. Los modales son fragmentos HTML que se piden con `fetch` (cabecera `X-Requested-With: fetch`); al guardar, el servidor responde 204 + `X-Despacho-Redirect`. Sin JS, el modal se abre como página. |
| Base de datos | **PostgreSQL** administrado | Transacciones, triggers para la bitácora inmutable, respaldos y PITR del proveedor. |
| Archivos | **Bucket S3 privado** (DigitalOcean Spaces) con versionado | Los PDF no pasan por disco del servidor; descarga con URL firmada de 5 min tras validar permisos. |
| Correo del sistema | **Resend** (API transaccional) | Plan gratuito suficiente (≈3,000 correos/mes); SPF/DKIM en el dominio del despacho. |
| Tareas | Comando `programador` en un *worker* de App Platform | Sin colas ni Redis; basta para 4–15 usuarios. |
| Despliegue | Docker; DigitalOcean App Platform | Sin administrar servidores; HTTPS automático. |
| CI | GitHub Actions | Lint (ruff), pruebas (pytest) y migraciones en cada push. |

### Modelo de datos (resumen)

Identificadores del dominio en español, igual que el prototipo.

- `Usuario` (correo, nombre, rol, activo) · roles: **Aprueba** (socio director), **Revisa**
  (abogado senior), **Elabora** (abogado), **Auxiliar**; bandera `es_admin` para Configuración.
- `Cliente` (razón social, RFC, representante, contacto, servicio, responsable) — en fase 1 solo lo
  necesario para ligar expedientes y archivos; se completa en fase 3.
- `Expediente` (número, año, juzgado, materia, tipo, cliente FK, contraparte, carácter, responsable,
  etapa, audiencia, estado, cuantía, esperando_auto, calendario de días inhábiles).
- `Accion` (expediente, recurso opcional, título, tipo, responsable, revisa, aprueba, plazo, estado,
  notas, acuse, terminada_el).
- `Recurso` (expediente, tipo, promovente, acto impugnado, número/toca, órgano, fecha interposición,
  etapa, suspensión, estado, resultado, fecha resolución, notas).
- `Acuerdo` (expediente, fecha, síntesis, acción a seguir, plazo, registrado_por).
- `EntradaBitacora` (expediente/cliente/trámite, fecha, texto, quién) — la bitácora visible; **solo alta**.
- `Documento` (expediente o cliente+carpeta, nombre, fecha, subido_por, clave S3, sha256, tamaño,
  eliminado_en). "Quitar" = baja lógica; el archivo se conserva.
- `EventoAuditoria` — ver abajo.
- `DiaInhabil` (calendario, fecha, descripción) y `Calendario` (p. ej. "Poder Judicial de Querétaro",
  "Poder Judicial de la Federación") — **fase 2**, aún no existen.
- `NotificacionEnviada` (acción, tipo, fecha) para no repetir correos.

### Roles y permisos

| Acción | Aprueba | Revisa | Elabora | Auxiliar |
|---|:-:|:-:|:-:|:-:|
| Ver todo el despacho | ✓ | ✓ | ✓ | ✓ |
| Registrar acuerdos, anotar bitácora, subir PDF | ✓ | ✓ | ✓ | ✓ |
| Crear/editar expedientes y acciones | ✓ | ✓ | ✓ | ✓ |
| Iniciar / enviar a revisión | ✓ | ✓ | ✓ | ✓ |
| **Aprobar** una acción | ✓ | solo si la acción no tiene aprobador y él es el revisor | — | — |
| Terminar una acción | ✓ | ✓ | ✓ | ✓ (con las reglas del flujo) |
| Quitar documentos, eliminar acciones y recursos (baja lógica) | ✓ | ✓ | ✓ | ✓ |
| Eliminar (baja lógica) expedientes | ✓ | — | — | — |
| Consultar la bitácora de auditoría | ✓ | — | — | — (salvo admin) |
| Usuarios (alta, rol, desactivar, enviar acceso) | admin | admin | admin | admin |

Aprobar una acción asignada a otro aprobador pide confirmación (como el prototipo) y queda registrado
en la auditoría (`aprobo_en_lugar_de`). En "editar acción" solo se puede regresar el estado o avanzar sin
saltarse la aprobación; "Terminada" solo con el botón Terminar. Implementado en `litigios/reglas.py`
(`puede_aprobar`) y `litigios/servicios.py` (`estados_permitidos_en_edicion`).

### Bitácora de auditoría inmutable
- Tabla `evento_auditoria`: fecha-hora, usuario, IP, acción (`crear`, `editar`, `cambiar_estado`,
  `aprobar`, `subir_archivo`, `descargar_archivo`, `iniciar_sesion`, …), entidad, id, datos antes/después (JSON).
- Se escribe en la misma transacción que el cambio (servicio `auditar()`; nunca desde la vista directamente).
- **Inmutable en la base**: trigger que lanza excepción en `UPDATE`, `DELETE` y `TRUNCATE`; el usuario
  de BD de la aplicación solo tiene `INSERT` y `SELECT` sobre la tabla.
- **Encadenada**: cada fila guarda `hash = sha256(hash_anterior + contenido)`; un comando nocturno
  verifica la cadena y avisa por correo si se rompe.
- Pantalla de consulta en Configuración (solo lectura, con filtros y exportación CSV).
- La `EntradaBitacora` visible en expedientes también es solo-alta (no hay botón de editar en el prototipo).

### Archivos PDF
- Solo PDF (se valida la firma `%PDF-` además de la extensión), máximo 50 MB por archivo.
- Clave: `clientes/{cliente_id}/expedientes/{expediente_id}/{uuid}.pdf` y
  `clientes/{cliente_id}/carpetas/{carpeta}/{uuid}.pdf`.
- Bucket privado con versionado; nunca URLs públicas. Cada descarga se audita.

### Plazos y días inhábiles
- Cómputo de días hábiles: excluye sábados, domingos y los días del calendario asignado al expediente
  (o al recurso: amparos usan el calendario federal por defecto).
- El semáforo sigue en días naturales (regla del prototipo); ver "Decisiones pendientes" #2.

### Notificaciones por correo
- Job diario 07:00 (hora de Ciudad de México): toda acción no terminada cuyo plazo **entra en rojo**
  (≤ 3 días naturales o vencida) y que no tenga ya una `NotificacionEnviada` de tipo `rojo` → un correo a
  responsable, revisor, aprobador y abogado responsable del expediente.
- También se evalúa al crear/editar una acción, para que un plazo que nace en rojo avise el mismo día.
- Correo en español con liga directa a la ficha del expediente.

### Respaldos (3-2-1)
1. Respaldos diarios del proveedor de BD con recuperación a un punto en el tiempo (7 días).
2. `pg_dump` cifrado nocturno a un bucket de **otro proveedor** (Backblaze B2), retención 30 diarios + 12 mensuales.
3. Versionado del bucket de PDF + réplica semanal a B2.
4. **Prueba de restauración mensual** documentada (un respaldo que no se ha restaurado no cuenta).

### Seguridad y privacidad
- HTTPS obligatorio, cookies seguras, CSRF, bloqueo tras intentos fallidos, sesión expira por inactividad.
- 2FA opcional (TOTP) en fase 5; obligatorio para admins si se decide.
- Datos personales: aviso de privacidad y medidas de seguridad conforme a la LFPDPPP (2025).

## 4. Plan por fases

### Fase 0 · Cimientos (≈ 1 semana)
- Proyecto Django, Docker, PostgreSQL local, ruff + pytest, GitHub Actions.
- Copiar `prototipo.html` a `docs/referencia/` y extraer su CSS a `static/css/despacho.css` sin cambios.
- Plantilla base con barra lateral, `head()`, tarjetas, chips, modales y toast del prototipo.
- Despliegue de un "hola mundo" con login al dominio definitivo.
- **Listo cuando**: se entra con usuario y contraseña en `https://…` y CI está en verde.

### Fase 1 · Litigios + usuarios + BD + archivos (≈ 4–6 semanas)
Alcance:
1. Usuarios, roles, login/logout, cambio y recuperación de contraseña por correo; alta de usuarios por admin.
2. Modelos y migraciones de: Cliente (mínimo), Expediente, Accion, Recurso, Acuerdo, EntradaBitacora,
   Documento, EventoAuditoria (con trigger y cadena de hash desde el día uno).
3. Pantallas de Litigios idénticas al prototipo: Tablero del día (métricas, leyenda, acuerdos de hoy,
   por actuar/esperando auto, apelaciones y amparos, por vencer, en espera de sentencia, terminados,
   filtro por materia), Expedientes (todos/urgentes/sentencia/terminados), Ficha del expediente,
   Acuerdos publicados, Apelaciones y amparos.
4. Todos los flujos y reglas de la sección 2 (acciones, esperando auto, semáforo, recursos, acuerdos),
   cálculo de plazo en días hábiles (sábados y domingos, como el prototipo).
5. "Expediente digitalizado" con carga y descarga real de PDF; carpeta del cliente para los PDF de sus litigios.
6. Informe al cliente (texto para copiar).
7. Calendario y Equipo y tareas, mostrando solo lo de litigios.
8. Consulta de la bitácora de auditoría (solo lectura).
9. Respaldos automáticos activos (BD + archivos) y primera prueba de restauración.
10. Importador del JSON "Exportar respaldo" del prototipo, por si ya hay datos capturados.
- Fuera de la fase 1: correo de plazos, días inhábiles, corporativo, trámites.
- **Listo cuando**: el equipo trabaja un expediente real de punta a punta, las pruebas cubren todas las
  reglas de la sección 2 y se restauró un respaldo con éxito.

### Fase 2 · Plazos: días inhábiles y notificaciones (≈ 2 semanas)
- Calendarios de días inhábiles (estatal y federal) editables en Configuración, con carga del año.
- Cómputo de plazos con días inhábiles; plazo calculado desde una fecha base elegible (hoy por defecto).
- Correo cuando un plazo entra en rojo; resumen diario opcional por usuario.
- Verificación nocturna de la cadena de auditoría con alerta.

### Fase 3 · Servicios corporativos (≈ 3–4 semanas)
- Tablero corporativo, Clientes, ficha del cliente con las 7 carpetas (PDF reales), contratos celebrados,
  contratos por celebrar con el flujo de aprobación, poderes, cumplimiento, contingencias
  (convertir en expediente), due diligence, informe al cliente. Calendario con vencimientos corporativos.

### Fase 4 · Trámites (≈ 2 semanas)
- Lista y ficha de trámite, etapas, documentos requeridos precargados por tipo (con PDF), "Bloquea",
  coadyuvantes, informe al cliente.

### Fase 5 · Endurecimiento (continuo)
- 2FA, exportaciones (Excel/PDF), búsqueda global, bitácora de accesos, monitoreo de disponibilidad,
  ajustes que surjan del uso real.

## 5. Cuentas que crea el despacho (no Claude)

Precios aproximados de lista a sep-2026, en USD, **más IVA 16%**; verificar al contratar.

| Cuenta | Para qué | Costo aprox. |
|---|---|---|
| GitHub (ya existe) | Código y CI | Gratis |
| DigitalOcean | App Platform: `web` (~$12) + `programador` (~$5) | ~$17/mes |
|  | PostgreSQL administrado (respaldos + PITR) | ~$15/mes |
|  | Spaces (PDF, 250 GB incluidos) | ~$5/mes |
| Dominio `.mx` o `.com.mx` (Akky, Neubox o similar) | `sistema.tudespacho.mx` | ~MXN 400–700/año |
| Resend | Correo del sistema (plazos, contraseñas) | Gratis hasta ~3,000/mes |
| Backblaze B2 | Copia externa de respaldos | ~$1–2/mes |
| Correo del despacho (opcional si ya tienen) | Buzones de las personas: Google Workspace o Microsoft 365 | ~$6–8 por usuario/mes |

Total del sistema: **≈ US$40–45/mes** (≈ MXN 750–850 con IVA) + dominio. Alternativa económica
(un solo servidor con Docker, ~US$20/mes) posible, pero con más mantenimiento: no recomendada.

## 6. Mapa del código

```
despacho/        settings (todo por variables de entorno), urls, settings_pruebas
cuentas/         Usuario (login por correo, roles), bloqueo por intentos, middleware de sesión obligatoria,
                 Configuración → Equipo (alta con invitación por correo)
auditoria/       EventoAuditoria + migración 0002 (triggers de inmutabilidad y cadena de hash en PostgreSQL),
                 servicios.auditar()/Actor, pantalla de consulta y CSV
litigios/        catalogos.py (copiados del prototipo) · reglas.py (funciones puras) · servicios.py (escrituras +
                 auditoría) · models.py · forms.py (formModal) · views.py · informes.py
                 management: cargar_ejemplo (seed del prototipo), importar_prototipo (JSON de "Exportar respaldo")
nucleo/          fechas.py (fmt, fmt_largo, días hábiles) · respaldos.py · comandos respaldar, verificar_auditoria,
                 programador
templates/       base.html (barra lateral del prototipo), modal_form.html, litigios/*, cuentas/*, registration/*
static/          css/despacho.css (CSS del prototipo sin cambios) · js/despacho.js
tests/           reglas, flujos, auditoría, web (pytest, contra PostgreSQL real)
ops/sql/roles.sql, .do/app.yaml, Dockerfile, docker-compose.yml, .github/workflows/ci.yml
docs/operacion.md  puesta en marcha, tareas automáticas, prueba de restauración mensual
```

## 7. Convenciones de trabajo

- Interfaz 100 % en español; textos copiados del prototipo cuando existan.
- Código: nombres del dominio en español (`expediente`, `accion`, `esperando_auto`); comentarios breves en español.
- Reglas de negocio en `litigios/reglas.py` (funciones puras: `urgencia`, `puede_terminar`, `siguiente_estado`,
  `sumar_dias_habiles`, …) con pruebas; las vistas no contienen reglas.
- Todo cambio de datos pasa por un servicio que escribe la auditoría en la misma transacción.
- No hay borrado físico de expedientes, acciones, documentos ni bitácoras.
- Rama de trabajo actual: `claude/despacho-juridico-arquitectura-ofa17c`. Commits pequeños y descriptivos.
- Antes de hacer push: `ruff check`, `pytest`, `python manage.py makemigrations --check`.
- Secretos solo en variables de entorno; nunca en el repositorio.

## 8. Decisiones

En la sesión 2 el despacho pidió construir sin esperar respuestas; se adoptaron las propuestas. Cualquiera
se puede revertir si el despacho lo pide.

1. ✅ (provisional) Aprueba cualquier usuario con rol Aprueba (confirmación + auditoría si no es el asignado);
   si la acción no tiene aprobador, su revisor puede aprobarla.
2. ✅ (provisional) Semáforo en días naturales, como el prototipo.
3. ✅ (provisional) Cliente capturado con lista de sugerencias (`datalist`); si no existe se crea al guardar.
4. ⏳ Correo por "más de 60 días sin actuación": propuesta de resumen semanal en fase 2.
5. ✅ (provisional) Todos ven todo, como el prototipo.
6. ⏳ Dominio y nombre definitivo (en `.do/app.yaml` está `sistema.tudespacho.mx` como marcador).
7. ✅ "Quitar" documento, eliminar acción/recurso: cualquiera (como el prototipo), siempre baja lógica.
   Eliminar expediente: solo rol Aprueba.
8. ✅ La bitácora visible y los acuerdos publicados son de solo alta en la base (no hay edición en el prototipo).

## 9. Estado actual

- [x] Plan y arquitectura (sesión 1, 24-sep-2026).
- [x] `docs/referencia/prototipo.html` subido (versión anterior, ver §1).
- [x] **Fase 0** en código: proyecto Django, PostgreSQL, CSS del prototipo, plantilla base, login, Docker,
      `.do/app.yaml`, CI. *Falta desplegar* (requiere las cuentas de §5).
- [x] **Fase 1** en código (sesión 2): usuarios/roles/login/recuperación, bloqueo por intentos, todos los modelos,
      auditoría inmutable encadenada, tablero, expedientes, ficha, acciones con flujo y aprobación, esperando auto,
      semáforo, acuerdos, apelaciones y amparos, PDF (subir/adjuntar/descargar/quitar), informe al cliente,
      calendario y equipo (solo litigios), consulta de auditoría, respaldos + programador, importador del prototipo,
      datos de ejemplo. 84 pruebas en verde; recorrido en navegador (escritorio y móvil) sin errores de JS.
- [x] `.do/app.yaml` reducido a la publicación inicial (app + base + PDF, rama de trabajo, `${APP_DOMAIN}`);
      correo, respaldos y worker `programador` se agregan después (ver comentarios del archivo).
- [ ] (sesión 3, en curso) El despacho está creando la cuenta de DigitalOcean: clúster `despacho-db`, Space
      `despacho-pdf`, luego App con el spec. Crear cuentas restantes de §5, primer administrador y **primera prueba de restauración** (docs/operacion.md §4).
      Con eso se cierra la fase 1 ("listo cuando": expediente real de punta a punta + restauración exitosa).
- [ ] Probar respaldos contra B2 real (el volcado y la restauración ya se probaron en local; la subida a S3 no).
- [ ] Fase 2: días inhábiles, correos de plazo en rojo (tabla `NotificacionEnviada` ya existe), resumen semanal.

### Cómo retomar
`pip install -r requirements-dev.txt`, PostgreSQL 16 local (`DATABASE_URL`), `python manage.py migrate`,
`python manage.py cargar_ejemplo`, `DJANGO_DEBUG=1 python manage.py runserver`. Usuarios de ejemplo:
`abraham@ejemplo.mx` (aprueba, admin), `yairsinio@`, `mariana@`, `diego@ejemplo.mx` · `despacho-demo-2026`.
