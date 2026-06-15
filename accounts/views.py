from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from .forms import UserRegistrationForm, EmailAuthenticationForm, ProfileForm, ChildForm
from .models import Child
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from enrollment.models import Enrollment  # Прямой импорт из твоей структуры

class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True


class RegisterView(CreateView):
    form_class = UserRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")

    def form_valid(self, form):
        return super().form_valid(form)

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("/")
        return super().dispatch(request, *args, **kwargs)
    

@login_required
def edit_profile(request):
    profile = request.user.profile
    
    # Ищем любые активные или оплаченные заявки этого родителя
    parent_enrollments = Enrollment.objects.filter(user=request.user)
    
    has_pending = parent_enrollments.filter(status__in=['submitted', 'under_review']).exists()
    has_paid_or_confirmed = parent_enrollments.filter(status__in=['approved', 'awaiting_payment', 'payment_review', 'paid']).exists()
    
    # Если есть хоть одна живая заявка в системе — важные данные менять нельзя
    can_edit = not (has_pending or has_paid_or_confirmed)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile, can_edit=can_edit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ваш профиль успешно обновлён.')
            return redirect('home:dashboard')
    else:
        form = ProfileForm(instance=profile, can_edit=can_edit)
        
    context = {
        'form': form,
        'can_edit': can_edit,
        'has_pending': has_pending,
        'has_paid_or_confirmed': has_paid_or_confirmed,
    }
    return render(request, 'accounts/edit_profile.html', context)


@login_required
def add_child(request):
    if request.method == 'POST':
        # Передаем user для валидатора clean() против дубликатов
        form = ChildForm(request.POST, user=request.user)
        if form.is_valid():
            child = form.save(commit=False)
            child.parent = request.user
            child.save()
            messages.success(request, f'Ребёнок {child.last_name} {child.first_name} добавлен.')
            return redirect('home:dashboard')
    else:
        form = ChildForm(user=request.user)
    return render(request, 'accounts/add_child.html', {'form': form})


@login_required
def edit_child(request, child_id):
    child = get_object_or_404(Child, id=child_id, parent=request.user)
    
    # Считаем активные или оплаченные/проверенные заявки по этому ребенку
    child_enrollments = Enrollment.objects.filter(child=child)
    
    has_pending = child_enrollments.filter(status='under_review').exists() or child_enrollments.filter(status='submitted').exists()
    has_paid_or_confirmed = child_enrollments.filter(status__in=['approved', 'awaiting_payment', 'payment_review', 'paid']).exists()
    
    # Если есть заявки на проверке или одобренные/оплаченные — can_edit блокируется
    can_edit = not (has_pending or has_paid_or_confirmed)
    
    if request.method == 'POST':
        if not can_edit:
            messages.error(request, 'Ошибка! Данные этого ребёнка заблокированы, так как они участвуют в активной заявке.')
            return redirect('home:dashboard')
            
        form = ChildForm(request.POST, instance=child, user=request.user, can_edit=can_edit)
        if form.is_valid():
            form.save()
            messages.success(request, f'Данные ребёнка {child.first_name} обновлены.')
            return redirect('home:dashboard')
    else:
        form = ChildForm(instance=child, user=request.user, can_edit=can_edit)
        
    context = {
        'form': form,
        'child': child,
        'can_edit': can_edit,
        'has_pending': has_pending,
        'has_paid_or_confirmed': has_paid_or_confirmed,
    }
    return render(request, 'accounts/edit_child.html', context)


@login_required
def delete_child(request, child_id):
    child = get_object_or_404(Child, id=child_id, parent=request.user)
    
    # Проверяем, привязан ли ребёнок к каким-либо заявкам (кроме отклонённых)
    active_apps = Enrollment.objects.filter(child=child).exclude(status='rejected')
    
    if active_apps.exists():
        messages.error(request, f'Невозможно удалить профиль {child.first_name}, так как он привязан к действующей заявке на обучение.')
        return redirect('home:dashboard')
        
    child.delete()
    messages.success(request, 'Профиль ребёнка успешно удалён из системы.')
    return redirect('home:dashboard')