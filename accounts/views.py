from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login
from django.contrib.auth.views import LoginView
from django.urls import reverse_lazy
from django.views.generic import CreateView
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User, Group
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .forms import UserRegistrationForm, EmailAuthenticationForm, ProfileForm, ChildForm
from .models import Profile, Child, RegistrationCode
from enrollment.models import Enrollment

# Вспомогательные функции проверки ролей для защиты функций
def is_parent(user):
    return user.is_authenticated and user.groups.filter(name='Родитель').exists()

def is_child(user):
    return user.is_authenticated and user.groups.filter(name='Ребёнок').exists()


class CustomLoginView(LoginView):
    template_name = "accounts/login.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = False  # Отключаем дефолтный джанговский редирект, делаем свой кастомный ниже

    # ЗАЩИТА: Если пользователь УЖЕ залогинен, не пускаем его на форму ввода логина
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home:dashboard")
        return super().dispatch(request, *args, **kwargs)

    # УМНЫЙ РОЛЕВОЙ РЕДИРЕКТ ПОСЛЕ УСПЕШНОГО ВХОДА
    type_name = "login"
    def get_success_url(self):
        user = self.request.user

        if user.is_staff and user.is_superuser:
            return reverse_lazy("dashboard_admin:course_list")

        if user.groups.filter(name="Бухгалтер").exists():
            return reverse_lazy("accountant:enrollment_list")

        if user.groups.filter(name="Преподаватель").exists():
            return reverse_lazy("teacher:group_list")

        if user.groups.filter(name="Ребёнок").exists():
            return reverse_lazy("home:dashboard")

        # По умолчанию — Родителю
        return reverse_lazy("home:dashboard")


class RegisterView(CreateView):
    form_class = UserRegistrationForm
    template_name = "accounts/register.html"
    success_url = reverse_lazy("accounts:login")

    # ЗАЩИТА: Если пользователь залогинен, страница регистрации для него полностью заблокирована
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect("home:dashboard")
        return super().dispatch(request, *args, **kwargs)


@login_required
def edit_profile(request):
    user = request.user
    
    # ЗАЩИТА: Редактировать профиль родителя может только Родитель
    if not is_parent(user):
        return render(request, 'home/access_denied.html')

    profile = user.profile
    parent_enrollments = Enrollment.objects.filter(user=user)
    has_pending = parent_enrollments.filter(status__in=['submitted', 'under_review']).exists()
    has_paid_or_confirmed = parent_enrollments.filter(status__in=['approved', 'awaiting_payment', 'payment_review', 'paid']).exists()
    
    can_edit = not (has_pending or has_paid_or_confirmed)
    
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=profile, can_edit=can_edit)
        if form.is_valid():
            form.save()
            messages.success(request, 'Ваш профиль успешно обновлён.')
            return redirect('home:dashboard')
    else:
        form = ProfileForm(instance=profile, can_edit=can_edit)
        
    return render(request, 'accounts/edit_profile.html', {
        'form': form, 'can_edit': can_edit, 'has_pending': has_pending, 'has_paid_or_confirmed': has_paid_or_confirmed
    })


@login_required
def add_child(request):
    # ЗАЩИТА: Только родитель имеет право добавлять детей
    if not is_parent(request.user):
        return render(request, 'home/access_denied.html')

    if request.method == 'POST':
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
    # ЗАЩИТА: Только родитель имеет право изменять данные детей
    if not is_parent(request.user):
        return render(request, 'home/access_denied.html')

    child = get_object_or_404(Child, id=child_id, parent=request.user)
    child_enrollments = Enrollment.objects.filter(child=child)
    has_pending = child_enrollments.filter(status='under_review').exists() or child_enrollments.filter(status='submitted').exists()
    has_paid_or_confirmed = child_enrollments.filter(status__in=['approved', 'awaiting_payment', 'payment_review', 'paid']).exists()
    
    can_edit = not (has_pending or has_paid_or_confirmed)
    
    if request.method == 'POST':
        if not can_edit:
            messages.error(request, 'Ошибка! Данные этого ребёнка заблокированы, так как они участвуют в активной заявке.')
            return redirect('home:dashboard')
            
        form = ChildForm(request.POST, instance=child, user=request.user, can_edit=can_edit)
        if form.is_valid():
            form.save()
            messages.success(request, f'Данные ребёнка {child.first_name} updated.')
            return redirect('home:dashboard')
    else:
        form = ChildForm(instance=child, user=request.user, can_edit=can_edit)
        
    return render(request, 'accounts/edit_child.html', {
        'form': form, 'child': child, 'can_edit': can_edit, 'has_pending': has_pending, 'has_paid_or_confirmed': has_paid_or_confirmed
    })


@login_required
def delete_child(request, child_id):
    # ЗАЩИТА: Только родитель имеет право удалять детей
    if not is_parent(request.user):
        return render(request, 'home/access_denied.html')

    child = get_object_or_404(Child, id=child_id, parent=request.user)
    if Enrollment.objects.filter(child=child).exclude(status='rejected').exists():
        messages.error(request, f'Невозможно удалить профиль ребенка, так как он привязан к действующей заявке.')
        return redirect('home:dashboard')
        
    child.delete()
    messages.success(request, 'Профиль ребёнка успешно удалён.')
    return redirect('home:dashboard')


@login_required
def generate_child_code(request):
    # ЗАЩИТА: Только родитель через АЯКС может запросить генерацию кода
    if not is_parent(request.user):
        return JsonResponse({'error': 'Доступно только для аккаунтов родителей'}, status=403)
        
    child_id = request.GET.get('child_id')
    if not child_id:
        return JsonResponse({'error': 'Не указан ID ребенка'}, status=400)
        
    child = get_object_or_404(Child, id=child_id, parent=request.user)
    RegistrationCode.objects.filter(child=child).delete()
    
    import secrets
    import string
    alphabet = string.ascii_uppercase + string.digits
    random_code = ''.join(secrets.choice(alphabet) for _ in range(11))
    
    RegistrationCode.objects.create(child=child, code=random_code)
    return JsonResponse({'status': 'success', 'code': random_code, 'expires_in': 120})


from django import forms

class ChildRegisterForm(forms.ModelForm):
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['email']
        widgets = {'email': forms.EmailInput(attrs={'class': 'form-control'})}
        
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Этот Email уже используется.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            raise forms.ValidationError("Пароли не совпадают.")
        return cleaned_data


# accounts/views.py

def child_check_code(request):
    if request.user.is_authenticated:
        return redirect("home:dashboard")

    if request.method == 'POST':
        input_code = request.POST.get('code', '').strip().upper()
        code_obj = RegistrationCode.objects.filter(code=input_code).first()
        
        if code_obj and code_obj.is_valid():
            # 🛡️ ЖЕСТКАЯ ПРОВЕРКА: Если у этого ребенка УЖЕ есть аккаунт в ИС, блокируем повторную регистрацию
            if code_obj.child.user is not None:
                messages.error(request, f'Ребёнок {code_obj.child.first_name} уже зарегистрирован в системе! Повторная настройка не требуется. Используйте обычный вход.')
                return redirect('accounts:login')

            request.session['verified_child_id'] = code_obj.child.id
            return redirect('accounts:child_register_data')
        else:
            messages.error(request, 'Введенный код не существует или устарел!')
            return redirect('accounts:child_check_code')
            
    return render(request, 'accounts/child_check_code.html')


# ШАГ 2 РЕГИСТРАЦИИ РЕБЕНКА
def child_register_data(request):
    # ЗАЩИТА: Авторизованным пользователям тут делать нечего
    if request.user.is_authenticated:
        return redirect("home:dashboard")

    child_id = request.session.get('verified_child_id')
    if not child_id:
        return redirect('accounts:child_check_code')
        
    child = get_object_or_404(Child, id=child_id)
    
    if request.method == 'POST':
        form = ChildRegisterForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = form.cleaned_data['email'].split('@')[0]
            if User.objects.filter(username=user.username).exists():
                user.username = f"{user.username}_{User.objects.count()}"
                
            user.first_name = child.first_name
            user.last_name = child.last_name
            user.set_password(form.cleaned_data['password1'])
            user.save()
            
            child_group, _ = Group.objects.get_or_create(name='Ребёнок')
            user.groups.add(child_group)
            
            Profile.objects.create(user=user, phone='—', license_accepted=True, consent_given=True)
            
            child.user = user
            child.save()
            
            RegistrationCode.objects.filter(child=child).delete()
            del request.session['verified_child_id']
            
            # Логиним пацана строго через наш кастомный бэкенд
            login(request, user, backend='accounts.backends.EmailBackend')
            return redirect('home:dashboard')
    else:
        form = ChildRegisterForm()
        
    return render(request, 'accounts/child_register_form.html', {'form': form, 'child': child})