"""
Views для аутентификации
Согласно ТЗ раздел 4 и 6.1
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from django.contrib.auth import authenticate
from django.contrib.auth import logout as django_logout
from django.conf import settings
from django.shortcuts import redirect
from django.views.decorators.http import require_http_methods
from drf_spectacular.utils import extend_schema, OpenApiParameter
from django.utils.translation import gettext_lazy as _

from ..serializers import CustomTokenObtainPairSerializer, LoginSerializer
from ..services.audit import log_login_attempt


@require_http_methods(['GET', 'POST'])
def browser_logout_view(request):
    """End a browser session opened through the backend URL."""
    django_logout(request)
    return redirect(getattr(settings, 'BROWSER_LOGOUT_REDIRECT_URL', '/admin/login/'))


class LoginRateThrottle(AnonRateThrottle):
    """Rate limiting для login эндпоинта - 5 попыток в минуту"""
    rate = '5/minute'


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Кастомный view для получения JWT токенов
    POST /api/v1/auth/login/
    """
    serializer_class = CustomTokenObtainPairSerializer
    # throttle_classes = [LoginRateThrottle]  # Временно отключено - требует redis
    
    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == 200:
            # Успешный вход
            user = authenticate(
                request,
                login=request.data.get('login') or request.data.get('username'),
                password=request.data.get('password')
            )
            if user:
                log_login_attempt(
                    user=user,
                    success=True,
                    ip_address=request.META.get('REMOTE_ADDR')
                )
        else:
            # Неудачная попытка
            log_login_attempt(
                user=None,
                success=False,
                ip_address=request.META.get('REMOTE_ADDR')
            )
        
        return response


@extend_schema(
    tags=['auth'],
    request=None,
    responses={200: {'description': 'Успешный выход из системы'}},
    description='Выход из системы (добавление refresh токена в blacklist)'
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def logout_view(request):
    """
    Выход из системы
    POST /api/v1/auth/logout/
    Добавляет refresh токен в blacklist
    """
    try:
        refresh_token = request.data.get('refresh')
        if not refresh_token:
            return Response(
                {'detail': _('Refresh токен обязателен'), 'code': 'refresh_required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        token = RefreshToken(refresh_token)
        token.blacklist()
        
        # Логируем выход
        from ..services.audit import log_action
        log_action(
            user=request.user,
            action='logout.success',
            payload={'ip_address': request.META.get('REMOTE_ADDR')}
        )
        
        return Response(
            {'detail': _('Успешный выход из системы')},
            status=status.HTTP_200_OK
        )
    except Exception as e:
        return Response(
            {'detail': _('Неверный токен'), 'code': 'invalid_token'},
            status=status.HTTP_400_BAD_REQUEST
        )
