from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .views import (
    UserViewSet, UserProfileViewSet, ScanViewSet, AppointmentViewSet,
    PaymentViewSet, NotificationViewSet, ConsultationViewSet,
    DoctorViewSet, AssistantViewSet, predict_scan, XRayImageViewSet,
    CreatorViewSet, predict_view, proxy_image
)

router = DefaultRouter()
router.register(r'users', UserViewSet)
router.register(r'profiles', UserProfileViewSet)
router.register(r'scans', ScanViewSet)
router.register(r'appointments', AppointmentViewSet)
router.register(r'payments', PaymentViewSet)
router.register(r'notifications', NotificationViewSet)
router.register(r'consultations', ConsultationViewSet)
router.register(r'doctors', DoctorViewSet)
router.register(r'assistants', AssistantViewSet, basename='assistant')
router.register(r'xrayimage', XRayImageViewSet, basename='xrayimage')
router.register(r'creators', CreatorViewSet, basename='creator')

urlpatterns = [
    path('', include(router.urls)),
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('predict-scan/', predict_scan, name='predict-scan'),
    path('predict/', predict_view, name='predict'),
    path('xray-analyze/', predict_scan, name='xray-analyze'),  # Alternative endpoint for clarity
    path('proxy-image/', proxy_image, name='proxy-image'),  # New endpoint for proxying images
] 