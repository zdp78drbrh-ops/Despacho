"""Carga los datos de ejemplo del prototipo (seed()) para Litigios. Solo para demostración y pruebas:
se niega a correr si ya hay expedientes."""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from auditoria.servicios import Actor
from litigios.models import Accion, Acuerdo, Cliente, Documento, EntradaBitacora, Expediente, Recurso
from nucleo.fechas import fmt, hoy

USUARIOS = [
    ("abraham@ejemplo.mx", "Abraham Jassen", "aprueba", True),
    ("yairsinio@ejemplo.mx", "Lic. Yairsinio García", "revisa", False),
    ("mariana@ejemplo.mx", "Lic. Mariana Ruiz", "elabora", False),
    ("diego@ejemplo.mx", "Diego Mora", "auxiliar", False),
]


class Command(BaseCommand):
    help = "Carga los datos de ejemplo del prototipo (solo con la base vacía)."

    def add_arguments(self, parser):
        parser.add_argument("--contrasena", default="despacho-demo-2026", help="Contraseña de los usuarios de ejemplo")

    @transaction.atomic
    def handle(self, *args, contrasena, **opts):
        if Expediente.todos.exists():
            raise CommandError("Ya hay expedientes: no se cargan datos de ejemplo.")
        cargar(contrasena)
        self.stdout.write(
            self.style.SUCCESS(f"Listo. Usuarios: {', '.join(u[0] for u in USUARIOS)} · contraseña: {contrasena}")
        )


def cargar(contrasena="despacho-demo-2026"):
    Usuario = get_user_model()
    us = {}
    for email, nombre, rol, admin in USUARIOS:
        u = Usuario.objects.filter(email=email).first() or Usuario.objects.create_user(
            email, nombre, contrasena, rol=rol, is_staff=admin, is_superuser=admin
        )
        us[nombre] = u
    A, Y, M, D = (us[n] for n in ("Abraham Jassen", "Lic. Yairsinio García", "Lic. Mariana Ruiz", "Diego Mora"))
    T = hoy()

    def d(n):
        return T + timedelta(days=n)

    def iso(s):
        from datetime import date

        return date.fromisoformat(s)

    clientes = {}

    def cli(razon):
        if razon not in clientes:
            clientes[razon] = Cliente.objects.create(razon=razon)
        return clientes[razon]

    def exp(
        numero,
        anio,
        juzgado,
        materia,
        tipo,
        cliente,
        contraparte,
        caracter,
        responsable,
        etapa,
        audiencia,
        estado,
        cuantia,
        esperando=False,
    ):
        return Expediente.objects.create(
            numero=numero,
            anio=anio,
            juzgado=juzgado,
            materia=materia,
            tipo=tipo,
            cliente=cli(cliente),
            contraparte=contraparte,
            caracter=caracter,
            responsable=responsable,
            etapa=etapa,
            audiencia=audiencia,
            estado=estado,
            cuantia=cuantia,
            esperando_auto=esperando,
        )

    def acc(e, titulo, tipo, resp, plazo, revisa, aprueba, estado, notas="", recurso=None, **kw):
        return Accion.objects.create(
            expediente=e,
            titulo=titulo,
            tipo=tipo,
            responsable=resp,
            plazo=plazo,
            revisa=revisa,
            aprueba=aprueba,
            estado=estado,
            notas=notas,
            recurso=recurso,
            **kw,
        )

    def bit(e, fecha, texto, quien):
        EntradaBitacora.objects.create(expediente=e, fecha=fecha, texto=texto, quien=quien, quien_nombre=quien.nombre)

    def doc(e, nombre, fecha, quien):
        Documento.objects.create(expediente=e, nombre=nombre, fecha=fecha, quien=quien, quien_nombre=quien.nombre)

    e1 = exp(
        "312/2025",
        "2025",
        "Juzgado 2° Civil, Querétaro",
        "Mercantil",
        "Oral mercantil",
        "Constructora del Bajío, S.A. de C.V.",
        "Grupo Torres, S.A.",
        "Actor",
        M,
        "Desahogo de pruebas",
        d(21),
        "activo",
        4850000,
    )
    acc(e1, "Escrito de designación de perito", "Promoción", M, d(3), Y, A, "revision", "Perito en ingeniería civil")
    acc(e1, "Preparar audiencia de desahogo", "Audiencia", A, d(21), None, None, "pendiente")
    acc(e1, "Solicitar copias certificadas", "Promoción", M, d(7), Y, A, "elaboracion")
    acc(
        e1,
        "Ofrecimiento de pruebas",
        "Promoción",
        M,
        d(-4),
        Y,
        A,
        "terminada",
        acuse="Acuse 19 sep",
        terminada_el=d(-4),
    )
    bit(e1, d(-11), "Se registró acuerdo: se tiene por contestada la demanda", M)
    bit(e1, d(-8), "Aprobado el escrito de ofrecimiento de pruebas", A)
    bit(e1, d(-4), "Se presentó ofrecimiento de pruebas, se adjuntó acuse", M)
    bit(e1, T, "Se registró acuerdo: se admite prueba pericial", D)
    for n, f, q in [
        ("01 Demanda inicial", iso("2025-03-12"), M),
        ("02 Auto admisorio", iso("2025-03-20"), D),
        ("03 Emplazamiento", iso("2025-04-08"), D),
        ("04 Contestación de demanda", iso("2025-04-28"), D),
        ("05 Ofrecimiento de pruebas", d(-4), M),
    ]:
        doc(e1, n, f, q)

    e2 = exp(
        "87/2026",
        "2026",
        "Juzgado 4° Familiar, Querétaro",
        "Familiar",
        "Divorcio",
        "Rodrigo Hernández",
        "Laura Peña",
        "Actor",
        Y,
        "Audiencia preliminar",
        d(13),
        "activo",
        None,
    )
    acc(e2, "Preparar audiencia preliminar", "Audiencia", Y, d(13), None, A, "pendiente")
    bit(e2, T, "Se registró acuerdo: se señala fecha de audiencia", D)
    doc(e2, "01 Demanda de divorcio", iso("2026-02-10"), Y)

    e3 = exp(
        "201/2024",
        "2024",
        "Juzgado 1° Civil, Querétaro",
        "Civil",
        "Ordinario civil",
        "Inmobiliaria Norte, S.A. de C.V.",
        "Sucesión de Pedro Álvarez",
        "Actor",
        A,
        "Emplazamiento",
        None,
        "activo",
        2100000,
    )
    acc(
        e3,
        "Promoción para impulsar emplazamiento por edictos",
        "Promoción",
        D,
        d(8),
        M,
        A,
        "pendiente",
        "Riesgo de caducidad",
    )
    bit(e3, d(-95), "Se solicitó búsqueda de domicilio del demandado", D)
    doc(e3, "01 Demanda", iso("2024-06-03"), A)

    e4 = exp(
        "95/2026",
        "2026",
        "Juzgado 3° Civil, Querétaro",
        "Mercantil",
        "Ejecutivo mercantil",
        "Transportes Vega, S. de R.L.",
        "Comercializadora Lima, S.A.",
        "Demandado",
        M,
        "Contestación",
        None,
        "activo",
        780000,
    )
    acc(e4, "Contestación de demanda", "Escrito", M, d(1), Y, A, "aprobada")
    bit(e4, d(-6), "Se recibió emplazamiento", D)

    e5 = exp(
        "140/2026",
        "2026",
        "Juzgado 1° Civil, Querétaro",
        "Mercantil",
        "Oral mercantil",
        "Transportes Vega, S. de R.L.",
        "Logística del Centro, S.A.",
        "Actor",
        M,
        "Contestación",
        None,
        "activo",
        350000,
        esperando=True,
    )
    bit(e5, d(-5), "Se presentó promoción solicitando se tenga por contestada en sentido negativo", M)

    e6 = exp(
        "63/2025",
        "2025",
        "Juzgado de Control, Querétaro",
        "Penal",
        "Carpeta de investigación",
        "Jorge Ramírez",
        "Ministerio Público",
        "Imputado",
        Y,
        "Presentación de demanda",
        None,
        "activo",
        None,
    )
    bit(e6, d(-66), "Se solicitó copia de la carpeta", Y)

    e7 = exp(
        "271/2024",
        "2024",
        "Juzgado 2° Civil, Querétaro",
        "Mercantil",
        "Oral mercantil",
        "Grupo Sierra, S.A. de C.V.",
        "Aceros Unidos, S.A.",
        "Actor",
        A,
        "Citado a sentencia",
        None,
        "sentencia",
        1900000,
    )
    bit(e7, d(-50), "Se presentaron alegatos", A)

    e8 = exp(
        "188/2023",
        "2023",
        "Juzgado 3° Civil, Querétaro",
        "Mercantil",
        "Ejecutivo mercantil",
        "Grupo Sierra, S.A. de C.V.",
        "Distribuidora Ochoa",
        "Actor",
        A,
        "Ejecución",
        None,
        "terminado",
        420000,
    )
    bit(e8, d(-120), "Sentencia favorable, se cobró el adeudo", A)

    e9 = exp(
        "44/2025",
        "2025",
        "Juzgado 5° Civil, Querétaro",
        "Civil",
        "Ordinario civil",
        "Inmobiliaria Norte, S.A. de C.V.",
        "Comercializadora Real, S.A.",
        "Actor",
        Y,
        "Apelación",
        None,
        "activo",
        3200000,
    )
    r1 = Recurso.objects.create(
        expediente=e9,
        tipo="Apelación",
        promovente="Contraparte",
        acto_impugnado=f"Sentencia definitiva del {fmt(d(-30), True)} (favorable a nosotros)",
        numero="Toca 512/2026",
        organo="Segunda Sala Civil del TSJ Querétaro",
        fecha_interposicion=d(-18),
        etapa="Contestación de agravios",
        suspension="No aplica",
        notas="La contraparte apeló en ambos efectos",
    )
    acc(e9, "Contestación de agravios", "Escrito", Y, d(5), M, A, "elaboracion", recurso=r1)
    bit(e9, d(-30), "Sentencia definitiva favorable", D)
    bit(e9, d(-18), "La contraparte interpuso apelación", D)
    bit(e9, d(-2), "Se notificó la admisión del recurso y corre plazo para contestar agravios", D)
    doc(e9, "12 Sentencia definitiva", d(-30), D)
    doc(e9, "13 Escrito de apelación de la contraparte", d(-18), D)

    e10 = exp(
        "PA-118/2026",
        "2026",
        "Dirección de Desarrollo Urbano, Municipio de Querétaro",
        "Administrativo",
        "Procedimiento de clausura",
        "Hotel Las Palmas, S.A. de C.V.",
        "Municipio de Querétaro",
        "Quejoso",
        A,
        "Amparo",
        d(16),
        "activo",
        None,
    )
    r2 = Recurso.objects.create(
        expediente=e10,
        tipo="Amparo indirecto",
        promovente="Nosotros",
        acto_impugnado=f"Orden de clausura y sellos del {fmt(d(-25), True)}",
        numero="9/2026",
        organo="Juzgado 1° de Distrito en Querétaro",
        fecha_interposicion=d(-22),
        etapa="Informes justificados",
        suspension="Definitiva concedida",
        notas="Audiencia constitucional señalada",
    )
    acc(e10, "Revisar informes justificados y objetar", "Escrito", A, d(9), Y, None, "pendiente", recurso=r2)
    acc(e10, "Preparar audiencia constitucional", "Audiencia", A, d(16), None, None, "pendiente", recurso=r2)
    bit(e10, d(-22), "Se presentó demanda de amparo indirecto", A)
    bit(e10, d(-20), "Se concedió la suspensión provisional", D)
    bit(e10, d(-12), "Audiencia incidental: se concedió la suspensión definitiva", A)
    doc(e10, "01 Demanda de amparo", d(-22), A)
    doc(e10, "02 Auto admisorio y suspensión provisional", d(-20), D)

    for fecha, e, s, a, p in [
        (T, e1, "Se admite prueba pericial en ingeniería", "Designar perito", d(3)),
        (T, e2, "Se señala audiencia preliminar", "Preparar audiencia", d(13)),
        (T, e5, "Se tiene por presentada la promoción, a sus autos", "Solo registrar", None),
        (d(-1), e4, "Se tiene por emplazado, corre término para contestar", "Contestar demanda", d(1)),
    ]:
        Acuerdo.objects.create(
            expediente=e, fecha=fecha, sintesis=s, accion=a, plazo=p, registrado_por=D, registrado_por_nombre=D.nombre
        )
    from auditoria.servicios import auditar

    auditar(Actor(), "cargar_ejemplo", None, entidad="sistema", descripcion="Se cargaron los datos de ejemplo")
    return us
