from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from apps.assistant.serializers import ChatRequestSerializer, ChatResponseSerializer
from apps.assistant.services.llm_client import (
    AssistantUnavailableError,
    AssistantUpstreamError,
    ask_assistant,
)
from apps.assistant.services.context import build_user_context


class AssistantChatView(APIView):
    """POST /api/assistant/chat/ — asistente de onboarding (no cobra créditos)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'assistant'

    def post(self, request):
        serializer = ChatRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        context = build_user_context(request.user, data['page'])
        try:
            result = ask_assistant([dict(m) for m in data['messages']], context)
        except AssistantUnavailableError:
            return Response({'detail': 'El asistente no está disponible.'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except AssistantUpstreamError:
            return Response({'detail': 'El asistente no pudo responder. Intenta de nuevo.'},
                            status=status.HTTP_502_BAD_GATEWAY)
        return Response(ChatResponseSerializer(result).data)
