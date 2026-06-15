from django.urls import path
from django.contrib.auth import views as auth_views
from .views import CustomLoginView, RegisterView
from . import views

app_name = 'accounts'

urlpatterns = [
    path("login/", CustomLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="/"), name="logout"),
    path("register/", RegisterView.as_view(), name="register"),
    path("profile/edit/", views.edit_profile, name='edit_profile'),
    path("child/add/", views.add_child, name='add_child'),
    path("child/edit/<int:child_id>/", views.edit_child, name='edit_child'), # Наш новый путь!
    path("child/delete/<int:child_id>/", views.delete_child, name='delete_child'),
]