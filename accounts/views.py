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
from .models import Profile, Child, RegistrationCode


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    # УДАЛИЛИ redirect_authenticated_user = True, чтобы Django не ломал кастомные редиректы

    # КАТЕГОРИЧЕСКИЙ СМАРТ-РЕДИРЕКТ ПОСЛЕ ЛОГИНА ПО РОЛЯМ
    def get_success_url(self):
        user = self.request.user

        # 1. Проверяем флаги глобального Администратора
        if user.is_staff and user.is_superuser:
            return reverse_lazy("dashboard_admin:course_list")

        # 2. Проверяем Бухгалтера
        if user.groups.filter(name="Бухгалтер").exists():
            return reverse_lazy("accountant:enrollment_list")

        # 3. Проверяем Преподавателя
        if user.groups.filter(name="Преподаватель").exists():
            return reverse_lazy("teacher:group_list")

        # 4. Проверяем Ребёнка (Ведёт на /home/, где views.dashboard сразу отрендерит кабинет)
        if user.groups.filter(name="Ребёнок").exists():
            return reverse_lazy("home:dashboard")

        # 5. По умолчанию (Родитель)
        return reverse_lazy("home:dashboard")


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

import secrets
import string
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from .models import Child, RegistrationCode

@login_required
def generate_child_code(request):
    if not request.user.groups.filter(name='Родитель').exists():
        return JsonResponse({'error': 'Доступно только для аккаунтов родителей'}, status=403)
        
    child_id = request.GET.get('child_id')
    if not child_id:
        return JsonResponse({'error': 'Не указан ID ребенка'}, status=400)
        
    # Проверяем, что этот ребенок реально принадлежит текущему родителю (защита от хакеров)
    child = get_object_or_404(Child, id=child_id, parent=request.user)
    
    # Стираем старый код именно ЭТОГО ребенка, если он был
    RegistrationCode.objects.filter(child=child).delete()
    
    # Генерируем 11-значный код
    alphabet = string.ascii_uppercase + string.digits
    random_code = ''.join(secrets.choice(alphabet) for _ in range(11))
    
    # Сохраняем в базу с привязкой к конкретному ребенку
    RegistrationCode.objects.create(child=child, code=random_code)
    
    return JsonResponse({
        'status': 'success',
        'code': random_code,
        'expires_in': 120
    })


# accounts/views.py
from django import forms
from django.contrib.auth.models import User, Group

class ChildRegisterForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Придумайте пароль'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Повторите пароль'}))

    class Meta:
        model = User
        fields = ['email'] # ФИО мы заберем автоматически из карточки ребенка, созданной родителем!
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'example@mail.ru'}),
        }
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Этот Email уже используется в системе.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            raise forms.ValidationError("Введенные пароли не совпадают.")
        return cleaned_data


# ШАГ 1: ПРОВЕРКА КОДА РЕБЕНКА С УЛИЦЫ
def child_check_code(request):
    if request.method == 'POST':
        input_code = request.POST.get('code', '').strip().upper()
        
        # Ищем код безопасности в нашей базе данных
        code_obj = RegistrationCode.objects.filter(code=input_code).first()
        
        if code_obj and code_obj.is_valid():
            # Код валидный! Запоминаем ID ребенка в сессии, чтобы пустить на Шаг 2
            request.session['verified_child_id'] = code_obj.child.id
            return redirect('accounts:child_register_data')
        else:
            messages.error(request, 'Введенный код не существует, либо истекли 2 минуты его действия!')
            return redirect('accounts:child_check_code')
            
    return render(request, 'accounts/child_check_code.html')


# ШАГ 2: СОЗДАНИЕ УЧЕТНОЙ ЗАПИСИ И НАЗНАЧЕНИЕ РОЛИ "РЕБЁНОК"
def child_register_data(request):
    child_id = request.session.get('verified_child_id')
    if not child_id:
        messages.error(request, 'Доступ заблокирован. Пожалуйста, введите код родителя.')
        return redirect('accounts:child_check_code')
        
    child = get_object_or_404(Child, id=child_id)
    
    if request.method == 'POST':
        form = ChildRegisterForm(request.POST)
        if form.is_valid():
            # Создаем учетку пользователя системы
            user = form.save(commit=False)
            user.username = form.cleaned_data['email'].split('@')[0]
            if User.objects.filter(username=user.username).exists():
                user.username = f"{user.username}_{User.objects.count()}"
                
            # Переносим настоящие ФИО, которые родитель указал в карточке!
            user.first_name = child.first_name
            user.last_name = child.last_name
            user.set_password(form.cleaned_data['password1'])
            user.save()
            
            # ЖЕСТКО НАЗНАЧАЕМ ТВОЮ НОВУЮ СИСТЕМНУЮ РОЛЬ (ГРУППУ) "Ребёнок"
            child_group, _ = Group.objects.get_or_create(name='Ребёнок')
            user.groups.add(child_group)
            
            # Создаем обязательный системный профиль
            Profile.objects.create(user=user, phone='—', license_accepted=True, consent_given=True)
            
            # Связываем созданного пользователя с объектом ребенка
            child.user = user
            child.save()
            
            # Удаляем отработавший одноразовый код из базы и чистим сессию
            RegistrationCode.objects.filter(child=child).delete()
            del request.session['verified_child_id']
            
            # Автоматически авторизуем ребенка в ИС
            login(request, user)
            messages.success(request, f'Добро пожаловать, {user.first_name}! Регистрация завершена.')
            return redirect('home:dashboard') # Потом сделаем ему кастомный редирект на его base
    else:
        form = ChildRegisterForm()
        
    return render(request, 'accounts/child_register_form.html', {'form': form, 'child': child})