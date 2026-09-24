from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class Rol(models.TextChoices):
    APRUEBA = "aprueba", "Socio director (aprueba)"
    REVISA = "revisa", "Abogado senior (revisa)"
    ELABORA = "elabora", "Abogado (elabora)"
    AUXILIAR = "auxiliar", "Auxiliar jurídico"


class UsuarioManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, nombre, password=None, **extra):
        if not email:
            raise ValueError("El correo es obligatorio")
        u = self.model(email=self.normalize_email(email).lower(), nombre=nombre, **extra)
        u.set_password(password)
        u.save(using=self._db)
        return u

    def create_superuser(self, email, nombre, password=None, **extra):
        extra.setdefault("rol", Rol.APRUEBA)
        return self.create_user(email, nombre, password, is_staff=True, is_superuser=True, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Integrante del despacho. No se borra: se desactiva (la auditoría lo referencia)."""

    email = models.EmailField("correo", unique=True)
    nombre = models.CharField("nombre", max_length=120, help_text="Como aparece en el sistema: Lic. Nombre Apellido")
    rol = models.CharField("rol", max_length=20, choices=Rol.choices, default=Rol.ELABORA)
    is_active = models.BooleanField("activo", default=True)
    is_staff = models.BooleanField(
        "administrador", default=False, help_text="Puede administrar el equipo y la configuración"
    )
    fecha_alta = models.DateTimeField(default=timezone.now)
    intentos_fallidos = models.PositiveSmallIntegerField(default=0)
    bloqueado_hasta = models.DateTimeField(null=True, blank=True)

    objects = UsuarioManager()
    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["nombre"]

    class Meta:
        verbose_name = "usuario"
        ordering = ["nombre"]

    def __str__(self):
        return self.nombre

    @property
    def puede_aprobar(self):
        return self.rol == Rol.APRUEBA

    @property
    def es_admin(self):
        return self.is_staff
