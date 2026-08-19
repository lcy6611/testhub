from rest_framework import generics, status, permissions
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
import os
import time
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.auth import login, logout
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from .models import User, UserProfile
from .serializers import UserSerializer, UserCreateSerializer, LoginSerializer, UserProfileSerializer

# JWT 相关导入
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_current_user(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
import os
import time
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.auth import login, logout

@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_current_user(request):
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

@method_decorator(csrf_exempt, name='dispatch')
class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserCreateSerializer
    permission_classes = [permissions.AllowAny]
    
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        # 安全地创建token
        try:
            from rest_framework.authtoken.models import Token
            token, created = Token.objects.get_or_create(user=user)
            token_key = token.key
        except ImportError:
            token_key = f"temp_token_{user.id}"
        
        return Response({
            'user': UserSerializer(user).data,
            'token': token_key
        }, status=status.HTTP_201_CREATED)

@api_view(['POST'])
@permission_classes([permissions.AllowAny])
@csrf_exempt
def login_view(request):
    print(f'[LOGIN_DEBUG] received body: {request.data!r}', flush=True)
    serializer = LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    user = serializer.validated_data['user']
    login(request, user)

    # JWT Token (优先使用JWT)
    refresh = RefreshToken.for_user(user)
    access_token = str(refresh.access_token)
    refresh_token = str(refresh)

    return Response({
        'user': UserSerializer(user).data,
        'access': access_token,       # JWT access token
        'refresh': refresh_token,     # JWT refresh token
        'message': '登录成功'
    })

@api_view(['POST'])
@csrf_exempt
def logout_view(request):
    """用户退出登录，将refresh token加入黑名单"""
    if request.user.is_authenticated:
        try:
            # 尝试将refresh token加入黑名单
            refresh_token = request.data.get('refresh')
            if refresh_token:
                from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
                from rest_framework_simplejwt.tokens import RefreshToken as JWTRefreshToken
                try:
                    token = JWTRefreshToken(refresh_token)
                    token.blacklist()
                except Exception as e:
                    print(f"Blacklist error: {e}")
        except Exception as e:
            print(f"Logout error: {e}")

        # 清除旧的auth token（向后兼容）
        try:
            request.user.auth_token.delete()
        except:
            pass

        logout(request)

    return Response({'message': '退出成功'})

@api_view(['GET'])
def profile_view(request):
    if not request.user.is_authenticated:
        return Response({'error': '未登录'}, status=status.HTTP_401_UNAUTHORIZED)
    
    serializer = UserSerializer(request.user)
    return Response(serializer.data)

class UserListView(generics.ListCreateAPIView):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

class UserDetailView(generics.RetrieveUpdateDestroyAPIView):
    queryset = User.objects.all().order_by('username')
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]


@api_view(['GET', 'PATCH'])
@permission_classes([permissions.IsAuthenticated])
def ui_settings_view(request):
    """获取/更新当前用户的界面偏好（主题模式、主题色、皮肤、壁纸）"""
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if request.method == 'GET':
        return Response(profile.ui_settings or {})

    # PATCH：增量合并
    incoming = request.data
    if not isinstance(incoming, dict):
        return Response({'error': '请求数据格式不正确'}, status=status.HTTP_400_BAD_REQUEST)

    current = profile.ui_settings or {}
    allowed_keys = {'mode', 'primary', 'skin', 'wallpaper', 'wallpaperFit', 'reducedMotion', 'hermes_avatar_enabled', 'hermes_eye_enabled', 'hermes_eye_style'}
    for k, v in incoming.items():
        if k in allowed_keys:
            current[k] = v
    profile.ui_settings = current
    profile.save()
    return Response(profile.ui_settings)


@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def wallpaper_upload_view(request):
    """上传自定义壁纸，返回可访问 URL（存于 media/wallpapers/）"""
    f = request.FILES.get('file')
    if not f:
        return Response({'error': '未找到上传文件'}, status=status.HTTP_400_BAD_REQUEST)

    allowed = {'image/jpeg', 'image/png', 'image/webp', 'image/gif'}
    if f.content_type not in allowed:
        return Response({'error': '仅支持 JPG/PNG/WEBP/GIF 图片'}, status=status.HTTP_400_BAD_REQUEST)
    if f.size > 5 * 1024 * 1024:
        return Response({'error': '图片不能超过 5MB'}, status=status.HTTP_400_BAD_REQUEST)

    ext = os.path.splitext(f.name)[1].lower() or '.jpg'
    rel_path = f'wallpapers/{request.user.id}_{int(time.time())}{ext}'
    saved_path = default_storage.save(rel_path, f)
    url = settings.MEDIA_URL + saved_path
    return Response({'url': url, 'name': f.name})