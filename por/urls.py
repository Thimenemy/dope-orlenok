from django.contrib import admin
from django.views.static import serve 
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("main.urls", namespace="main")),
    path("accounts/", include("accounts.urls")),
    path("home/", include("home.urls")),
    path("enrollment/", include("enrollment.urls")),
    path("accountant/", include("accountant.urls")),
    path('teacher/', include('teacher.urls')),
    path("chat/", include("chat.urls")), 
]


if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)