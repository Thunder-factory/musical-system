from rest_framework import serializers

MAX_MESSAGES = 12


class ChatMessageSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['user', 'assistant'])
    content = serializers.CharField(min_length=1, max_length=1000, trim_whitespace=True)


class ChatRequestSerializer(serializers.Serializer):
    messages = ChatMessageSerializer(many=True, allow_empty=False)
    page = serializers.CharField(max_length=100, required=False, allow_blank=True, default='')

    def validate_messages(self, value):
        if len(value) > MAX_MESSAGES:
            raise serializers.ValidationError(f'Máximo {MAX_MESSAGES} mensajes.')
        for index, message in enumerate(value):
            expected = 'user' if index % 2 == 0 else 'assistant'
            if message['role'] != expected:
                raise serializers.ValidationError(
                    'Los roles deben alternarse empezando por "user".'
                )
        if value[-1]['role'] != 'user':
            raise serializers.ValidationError('El último mensaje debe ser del usuario.')
        return value


class ChatActionSerializer(serializers.Serializer):
    label = serializers.CharField()
    route = serializers.CharField()


class ChatResponseSerializer(serializers.Serializer):
    reply = serializers.CharField()
    actions = ChatActionSerializer(many=True)
