import pytest

from auditoria.servicios import Actor


@pytest.fixture
def usuarios(db):
    from django.contrib.auth import get_user_model

    U = get_user_model()
    mk = lambda e, n, r, **kw: U.objects.create_user(e, n, "clave-de-prueba-123", rol=r, **kw)  # noqa: E731
    return {
        "A": mk("a@x.mx", "Abraham Jassen", "aprueba", is_staff=True),
        "A2": mk("a2@x.mx", "Otra Socia", "aprueba"),
        "Y": mk("y@x.mx", "Lic. Yairsinio García", "revisa"),
        "M": mk("m@x.mx", "Lic. Mariana Ruiz", "elabora"),
        "D": mk("d@x.mx", "Diego Mora", "auxiliar"),
    }


@pytest.fixture
def actor(usuarios):
    return lambda clave: Actor(usuario=usuarios[clave], ip="127.0.0.1")


@pytest.fixture
def expediente(usuarios, actor):
    from litigios import servicios

    return servicios.crear_expediente(
        actor("M"),
        {
            "numero": "312/2025",
            "anio": "2025",
            "juzgado": "Juzgado 2° Civil, Querétaro",
            "materia": "Mercantil",
            "tipo": "Oral mercantil",
            "cliente_nombre": "Constructora del Bajío, S.A. de C.V.",
            "caracter": "Actor",
            "contraparte": "Grupo Torres, S.A.",
            "responsable": usuarios["M"],
            "etapa": "Desahogo de pruebas",
            "audiencia": None,
            "cuantia": None,
        },
    )


@pytest.fixture
def cliente_web(client, usuarios):
    def entrar(clave):
        client.force_login(usuarios[clave])
        return client

    return entrar
