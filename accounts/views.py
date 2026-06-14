from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import UserRegistrationForm, EmailAuthenticationForm, ProfileForm, ChildForm
from .models import Child
from django.contrib.auth.decorators import login_required
from django.contrib import messages


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class RegisterView(CreateView):
    form_class = UserRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        # Здесь можно добавить автоматический вход после регистрации
        response = super().form_valid(form)
        # user = form.save()  # не нужно, так как save уже вызывается
        # login(self.request, user)  # раскомментируйте, если нужно сразу входить
        return response

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("/")  # или куда нужно
        return super().dispatch(request, *args, **kwargs)
    
@login_required
def edit_profile(request):
    profile = request.user.profile
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ваш профиль успешно обновлён.')
            return redirect('home:dashboard')
    else:
        form = ProfileForm(instance=profile)
    return render(request, 'accounts/edit_profile.html', {'form': form})

@login_required
def add_child(request):
    if request.method == 'POST':
        form = ChildForm(request.POST)
        if form.is_valid():
            child = form.save(commit=False)
            child.parent = request.user
            child.save()
            messages.success(request, f'Ребёнок {child.last_name} {child.first_name} добавлен.')
            return redirect('home:dashboard')
    else:
        form = ChildForm()
    return render(request, 'accounts/add_child.html', {'form': form})

@login_required
def delete_child(request, child_id):
    child = get_object_or_404(Child, id=child_id, parent=request.user)
    child.delete()
    messages.success(request, 'Ребёнок удалён.')
    return redirect('home:dashboard')
