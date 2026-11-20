"""Serializers de validación para administración de usuarios en reportes."""

from rest_framework import serializers


class AdminUserUpdateSerializer(serializers.Serializer):
    """Valida los campos editables por un administrador sobre un usuario."""

    is_staff = serializers.BooleanField(required=False)
    is_active = serializers.BooleanField(required=False)
    role = serializers.ChoiceField(choices=['admin', 'user'], required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError(
                'Debes enviar al menos un campo para actualizar (is_staff, is_active o role).'
            )
        if 'is_staff' in attrs and 'role' in attrs:
            expected_staff = attrs['role'] == 'admin'
            if attrs['is_staff'] != expected_staff:
                raise serializers.ValidationError(
                    'Los valores de is_staff y role son inconsistentes entre sí.'
                )
        return attrs
