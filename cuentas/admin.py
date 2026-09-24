from django.contrib import admin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ("nombre", "email", "rol", "is_active", "is_staff")
    list_filter = ("rol", "is_active", "is_staff")
    search_fields = ("nombre", "email")
    exclude = ("password", "user_permissions", "groups")
    readonly_fields = ("last_login", "fecha_alta")
