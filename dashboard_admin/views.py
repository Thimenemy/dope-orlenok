from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from main.models import Course
from django import forms
from django.db.models import Q

# Проверка: является ли пользователь администратором системы
def is_admin(user):
    return user.is_authenticated and user.is_staff and user.is_superuser

# Форма Django для создания и изменения параметров курса
class CourseAdminForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'description', 'price', 'duration', 'format', 'age_min', 'age_max', 'max_groups', 'slots_per_group', 'available']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control form-control-custom', 'placeholder': 'Например: Управление БПЛА'}),
            'description': forms.Textarea(attrs={'class': 'form-control form-control-custom', 'rows': 4, 'placeholder': 'Описание программы...'}),
            'price': forms.NumberInput(attrs={'class': 'form-control form-control-custom'}),
            'duration': forms.TextInput(attrs={'class': 'form-control form-control-custom', 'placeholder': 'Например: 14 дней'}),
            'format': forms.TextInput(attrs={'class': 'form-control form-control-custom', 'placeholder': 'Например: очно / онлайн'}),
            'age_min': forms.NumberInput(attrs={'class': 'form-control form-control-custom'}),
            'age_max': forms.NumberInput(attrs={'class': 'form-control form-control-custom'}),
            'max_groups': forms.NumberInput(attrs={'class': 'form-control form-control-custom'}),
            'slots_per_group': forms.NumberInput(attrs={'class': 'form-control form-control-custom'}),
            'available': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

@login_required
@user_passes_test(is_admin)
def admin_course_list(request):
    # Администратор видит абсолютно все курсы, включая архивные (available=False)
    courses = Course.objects.all().order_by('name')
    return render(request, 'dashboard_admin/course_list.html', {
        'courses': courses,
        'base_template': 'dashboard_admin/base_admin.html'
    })

@login_required
@user_passes_test(is_admin)
def admin_course_create(request):
    if request.method == 'POST':
        form = CourseAdminForm(request.POST)
        if form.is_valid():
            course = form.save()
            messages.success(request, f'Образовательная программа "{course.name}" успешно добавлена в каталог.')
            return redirect('dashboard_admin:course_list')
    else:
        form = CourseAdminForm()
    return render(request, 'dashboard_admin/course_form.html', {
        'form': form,
        'title': 'Добавление новой программы',
        'base_template': 'dashboard_admin/base_admin.html'
    })

@login_required
@user_passes_test(is_admin)
def admin_course_edit(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        form = CourseAdminForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f'Параметры курса "{course.name}" успешно обновлены.')
            return redirect('dashboard_admin:course_list')
    else:
        form = CourseAdminForm(instance=course)
    return render(request, 'dashboard_admin/course_form.html', {
        'form': form,
        'course': course,
        'title': f'Редактирование: {course.name}',
        'base_template': 'dashboard_admin/base_admin.html'
    })

from django import forms
from django.contrib.auth.models import User, Group
from accounts.models import Profile # Если сотрудникам тоже нужен пустой профиль в базе

# Форма создания сотрудника
class StaffCreateForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Электронная почта", 
                             widget=forms.EmailInput(attrs={'class': 'form-control form-control-custom'}))
    first_name = forms.CharField(required=True, label="Имя", 
                                 widget=forms.TextInput(attrs={'class': 'form-control form-control-custom'}))
    last_name = forms.CharField(required=True, label="Фамилия", 
                                widget=forms.TextInput(attrs={'class': 'form-control form-control-custom'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control form-control-custom'}), label="Пароль")
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control form-control-custom'}), label="Подтверждение пароля")
    
    # Выбор роли сотрудника
    ROLE_CHOICES = [
        ('Преподаватель', 'Преподаватель'),
        ('Бухгалтер', 'Бухгалтер'),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Роль / Должность", 
                             widget=forms.Select(attrs={'class': 'form-select form-select-custom'}))

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Пользователь с таким email уже существует в системе.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 and p2 and p1 != p2:
            raise forms.ValidationError("Пароли не совпадают.")
        return cleaned_data


# ВЬЮХА СПИСКА СОТРУДНИКОВ
@login_required
@user_passes_test(is_admin)
def admin_staff_list(request):
    staff_users = User.objects.filter(
        Q(is_staff=True) | 
        Q(groups__name__in=['Бухгалтер', 'Преподаватель'])
    ).distinct().exclude(id=request.user.id).order_by('-date_joined')
    
    return render(request, 'dashboard_admin/staff_list.html', {
        'staff_users': staff_users,
        'base_template': 'dashboard_admin/base_admin.html'
    })


# ВЬЮХА СОЗДАНИЯ СОТРУДНИКА
@login_required
@user_passes_test(is_admin)
def admin_staff_create(request):
    if request.method == 'POST':
        form = StaffCreateForm(request.POST)
        if form.is_valid():
            # Создаем объект юзера, но пока не сохраняем в базу железно
            user = form.save(commit=False)
            
            # Генерируем уникальный username на основе email (как у тебя в регистрации)
            user.username = form.cleaned_data['email'].split('@')[0]
            if User.objects.filter(username=user.username).exists():
                user.username = f"{user.username}_{User.objects.count()}"
                
            user.is_staff = True # Даем статус сотрудника аппаратно
            user.set_password(form.cleaned_data['password1']) # Хэшируем пароль безопасности ради
            user.save() # Сохраняем учетку в бд
            
            # Привязываем к выбранной группе (роли)
            selected_role = form.cleaned_data['role']
            group, created = Group.objects.get_or_create(name=selected_role)
            user.groups.add(group)
            
            # Создаем пустой профиль в accounts.models (чтобы не падало при проверке телефонов)
            Profile.objects.get_or_create(user=user, phone='—', license_accepted=True, consent_given=True)
            
            messages.success(request, f'Сотрудник {user.get_full_name()} успешно зарегистрирован как {selected_role}!')
            return redirect('dashboard_admin:staff_list')
    else:
        form = StaffCreateForm()
        
    return render(request, 'dashboard_admin/staff_form.html', {
        'form': form,
        'title': 'Регистрация нового сотрудника',
        'base_template': 'dashboard_admin/base_admin.html'
    })


# dashboard_admin/views.py

from django import forms
from django.contrib.auth.models import User, Group
from django.db.models import Q
from django.views.decorators.http import require_POST
from teacher.models import Group as CourseGroup # Импортируем модель групп, чтобы проверить, привязан ли препод

# Форма РЕДАКТИРОВАНИЯ сотрудника
class StaffEditForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Электронная почта", 
                             widget=forms.EmailInput(attrs={'class': 'form-control form-control-custom'}))
    first_name = forms.CharField(required=True, label="Имя", 
                                 widget=forms.TextInput(attrs={'class': 'form-control form-control-custom'}))
    last_name = forms.CharField(required=True, label="Фамилия", 
                                widget=forms.TextInput(attrs={'class': 'form-control form-control-custom'}))
    
    # Пароли делаем необязательными (blank=True) при изменении
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control form-control-custom'}), 
                                label="Новый пароль (оставьте пустым, если не хотите менять)", required=False)
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control form-control-custom'}), 
                                label="Подтверждение нового пароля", required=False)
    
    ROLE_CHOICES = [
        ('Преподаватель', 'Преподаватель'),
        ('Бухгалтер', 'Бухгалтер'),
    ]
    role = forms.ChoiceField(choices=ROLE_CHOICES, label="Роль / Должность", 
                             widget=forms.Select(attrs={'class': 'form-select form-select-custom'}))

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        can_edit_fields = kwargs.pop('can_edit_fields', True)
        super().__init__(*args, **kwargs)
        
        # Если сотрудник задействован — аппаратно запрещаем менять ФИО и Почту, даем сменить только пароль/роль
        if not can_edit_fields:
            self.fields['email'].disabled = True
            self.fields['first_name'].disabled = True
            self.fields['last_name'].disabled = True
            self.fields['role'].disabled = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        # Проверяем уникальность email среди других пользователей
        if User.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Пользователь с таким email уже зарегистрирован.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        p1 = cleaned_data.get('password1')
        p2 = cleaned_data.get('password2')
        if p1 or p2:
            if p1 != p2:
                raise forms.ValidationError("Новые пароли не совпадают.")
        return cleaned_data


# ВЬЮХА РЕДАКТИРОВАНИЯ
@login_required
@user_passes_test(is_admin)
def admin_staff_edit(request, user_id):
    staff_user = get_object_or_404(
        User, 
        Q(is_staff=True) | Q(groups__name__in=['Бухгалтер', 'Преподаватель']),
        id=user_id
    )
    
    # БИЗНЕС-ЛОГИКА ПРОВЕРКИ ЗАДЕЙСТВОВАННОСТИ
    # 1. Проверяем, привязан ли он как препод к физическим учебным группам
    has_groups = CourseGroup.objects.filter(teacher=staff_user).exists()
    # 2. Можешь расширить: например, проверял ли бухгалтер хоть одну заявку (если есть лог действий)
    
    # Если он нигде не задействован — разрешаем менять все поля (can_edit_fields = True)
    can_edit_fields = not has_groups

    if request.method == 'POST':
        form = StaffEditForm(request.POST, instance=staff_user, can_edit_fields=can_edit_fields)
        if form.is_valid():
            user = form.save(commit=False)
            
            # Если админ ввёл новый пароль — хэшируем и сохраняем его
            new_password = form.cleaned_data.get('password1')
            if new_password:
                user.set_password(new_password)
                
            user.save()
            
            # Обновляем группу (роль) сотрудника
            selected_role = form.cleaned_data['role']
            staff_user.groups.clear() # Сбрасываем старую роль
            group, created = Group.objects.get_or_create(name=selected_role)
            staff_user.groups.add(group)
            
            messages.success(request, f'Данные сотрудника {user.get_full_name()} успешно обновлены.')
            return redirect('dashboard_admin:staff_list')
    else:
        # GET-запрос: подтягиваем текущую роль в начальное значение
        current_role = staff_user.groups.first().name if staff_user.groups.exists() else 'Преподаватель'
        form = StaffEditForm(instance=staff_user, initial={'role': current_role}, can_edit_fields=can_edit_fields)
        
    return render(request, 'dashboard_admin/staff_form.html', {
        'form': form,
        'title': f'Редактирование сотрудника: {staff_user.get_full_name()}',
        'base_template': 'dashboard_admin/base_admin.html',
        'can_edit_fields': can_edit_fields
    })


# ВЬЮХА УДАЛЕНИЯ (БЕЗОПАСНАЯ ПОСТ-ОТПРАВКА)
@login_required
@user_passes_test(is_admin)
@require_POST
def admin_staff_delete(request, user_id):
    staff_user = get_object_or_404(
        User, 
        Q(is_staff=True) | Q(groups__name__in=['Бухгалтер', 'Преподаватель']),
        id=user_id
    )
    
    # Жесткая проверка перед удалением
    if CourseGroup.objects.filter(teacher=staff_user).exists():
        messages.error(request, f'Критическая ошибка удаления! {staff_user.get_full_name()} не может быть удален, так как он назначен преподавателем в активных учебных группах лагеря.')
        return redirect('dashboard_admin:staff_list')
        
    # Если проверок нет — удаляем учетку и связанный профиль
    staff_name = staff_user.get_full_name()
    staff_user.delete()
    messages.success(request, f'Учетная запись сотрудника "{staff_name}" навсегда удалена из базы данных системы.')
    return redirect('dashboard_admin:staff_list')



# dashboard_admin/views.py

from django.contrib.auth.models import User, Group
from django.db.models import Sum, Q
from accounts.models import Profile, Child
from teacher.models import GroupMember, StudentCourseReport

# Форма СОЗДАНИЯ родителя
class ParentCreateForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Email (Логин)", widget=forms.EmailInput(attrs={'class': 'form-control form-control-custom'}))
    first_name = forms.CharField(required=True, label="Имя", widget=forms.TextInput(attrs={'class': 'form-control form-control-custom'}))
    last_name = forms.CharField(required=True, label="Фамилия", widget=forms.TextInput(attrs={'class': 'form-control form-control-custom'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control form-control-custom'}), label="Пароль")
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control form-control-custom'}), label="Подтверждение пароля")

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("Этот email уже занят.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') != cleaned_data.get('password2'):
            raise forms.ValidationError("Пароли не совпадают.")
        return cleaned_data

# Форма РЕДАКТИРОВАНИЯ родителя
class ParentEditForm(forms.ModelForm):
    email = forms.EmailField(required=True, label="Email (Логин)", widget=forms.EmailInput(attrs={'class': 'form-control form-control-custom'}))
    first_name = forms.CharField(required=True, label="Имя", widget=forms.TextInput(attrs={'class': 'form-control form-control-custom'}))
    last_name = forms.CharField(required=True, label="Фамилия", widget=forms.TextInput(attrs={'class': 'form-control form-control-custom'}))
    password1 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control form-control-custom'}), label="Новый пароль (оставьте пустым)", required=False)
    password2 = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control form-control-custom'}), label="Подтверждение пароля", required=False)

    class Meta:
        model = User
        fields = ['email', 'first_name', 'last_name']

    def __init__(self, *args, **kwargs):
        can_edit_fields = kwargs.pop('can_edit_fields', True)
        super().__init__(*args, **kwargs)
        if not can_edit_fields:
            self.fields['email'].disabled = True
            self.fields['first_name'].disabled = True
            self.fields['last_name'].disabled = True

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if User.objects.filter(email=email).exclude(id=self.instance.id).exists():
            raise forms.ValidationError("Этот email уже зарегистрирован.")
        return email

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('password1') and cleaned_data.get('password1') != cleaned_data.get('password2'):
            raise forms.ValidationError("Новые пароли не совпадают.")
        return cleaned_data


# 1. ВЬЮХА СПИСКА РОДИТЕЛЕЙ С CRM-АНАЛИТИКОЙ
@login_required
@user_passes_test(is_admin)
def admin_parent_list(request):
    # Берем всех юзеров из группы "Родитель"
    parents = User.objects.filter(groups__name='Родитель').order_by('-date_joined')
    
    # Собираем аналитику для каждого родителя «на лету»
    for parent in parents:
        # Дети родителя
        parent_children = Child.objects.filter(parent=parent)
        parent.children_list = parent_children
        
        # Активные зачисления в группы и даты вступления
        parent.memberships = GroupMember.objects.filter(child__in=parent_children).select_related('group__course', 'child')
        
        # Завершенные курсы (проверяем наличие сгенерированных финальных отчетов/сертификатов)
        parent.completed_courses = StudentCourseReport.objects.filter(student__in=parent_children).select_related('group__course', 'student')
        
        # Финансы: Считаем сумму всех успешных оплат (status='paid') по заявкам родителя
        total_paid = parent.enrollments.filter(status='paid').aggregate(sum_price=Sum('price'))['sum_price'] or 0
        parent.total_paid_money = total_paid

    return render(request, 'dashboard_admin/parent_list.html', {
        'parents': parents,
        'base_template': 'dashboard_admin/base_admin.html'
    })


# 2. ВЬЮХА ДОБАВЛЕНИЯ РОДИТЕЛЯ
@login_required
@user_passes_test(is_admin)
def admin_parent_create(request):
    if request.method == 'POST':
        form = ParentCreateForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.username = form.cleaned_data['email'].split('@')[0]
            if User.objects.filter(username=user.username).exists():
                user.username = f"{user.username}_{User.objects.count()}"
            user.set_password(form.cleaned_data['password1'])
            user.save()
            
            # Назначаем роль
            group, _ = Group.objects.get_or_create(name='Родитель')
            user.groups.add(group)
            
            # Генерируем обязательный профиль
            Profile.objects.create(user=user, phone='—', license_accepted=True, consent_given=True)
            
            messages.success(request, f'Родитель {user.get_full_name()} успешно добавлен.')
            return redirect('dashboard_admin:parent_list')
    else:
        form = ParentCreateForm()
    return render(request, 'dashboard_admin/parent_form.html', {'form': form, 'title': 'Регистрация родителя', 'base_template': 'dashboard_admin/base_admin.html'})


# 3. ВЬЮХА ИЗМЕНЕНИЯ РОДИТЕЛЯ
@login_required
@user_passes_test(is_admin)
def admin_parent_edit(request, user_id):
    parent_user = get_object_or_404(User, groups__name='Родитель', id=user_id)
    
    # Блокировка: если дети родителя зачислены в группы — ФИО и Email менять нельзя
    has_active_students = GroupMember.objects.filter(child__parent=parent_user).exists()
    can_edit_fields = not has_active_students

    if request.method == 'POST':
        form = ParentEditForm(request.POST, instance=parent_user, can_edit_fields=can_edit_fields)
        if form.is_valid():
            user = form.save(commit=False)
            if form.cleaned_data.get('password1'):
                user.set_password(form.cleaned_data['password1'])
            user.save()
            messages.success(request, f'Данные родителя {user.get_full_name()} обновлены.')
            return redirect('dashboard_admin:parent_list')
    else:
        form = ParentEditForm(instance=parent_user, can_edit_fields=can_edit_fields)
        
    return render(request, 'dashboard_admin/parent_form.html', {
        'form': form,
        'title': f'Редактирование профиля: {parent_user.get_full_name()}',
        'base_template': 'dashboard_admin/base_admin.html',
        'can_edit_fields': can_edit_fields
    })


# 4. ВЬЮХА УДАЛЕНИЯ РОДИТЕЛЯ
@login_required
@user_passes_test(is_admin)
@require_POST
def admin_parent_delete(request, user_id):
    parent_user = get_object_or_404(User, groups__name='Родитель', id=user_id)
    
    # Проверка: если дети учатся, удалять аккаунт нельзя, иначе рухнет структура лагеря
    if GroupMember.objects.filter(child__parent=parent_user).exists():
        messages.error(request, f'Невозможно удалить аккаунт {parent_user.get_full_name()}! Его дети зачислены в учебные группы.')
        return redirect('dashboard_admin:parent_list')
        
    parent_name = parent_user.get_full_name()
    parent_user.delete()
    messages.success(request, f'Аккаунт родителя "{parent_name}" и профили его детей удалены.')
    return redirect('dashboard_admin:parent_list')


# dashboard_admin/views.py

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model

# ИМПОРТИРУЕМ СТРОГО ТВОИ МОДЕЛИ ИЗ ТВОЕГО ПРИЛОЖЕНИЯ CHAT
from chat.models import ChatRoom, ChatMessage

User = get_user_model()

@login_required
@user_passes_test(is_admin)  # Твоя функция проверки прав администратора
def admin_chat_list(request):
    # 1. Получаем все чаты админа (исключая скрытые им в deleted_for), сортируем по обновлению
    rooms = request.user.chat_rooms.exclude(deleted_for=request.user).order_by('-updated_at')
    
    rooms_data = []
    for room in rooms:
        # Формируем имя чата один в один как в твоём chat_list
        if room.room_type == 'group':
            display_name = room.name or 'Групповой чат'
        else:
            other = room.participants.exclude(id=request.user.id).first()
            if other:
                display_name = f"{other.last_name} {other.first_name}".strip() or other.username
            else:
                display_name = 'Неизвестный участник'
        
        # Считаем нечитанные сообщения для админа на основе твоего M2M поля read_by
        unread_count = room.messages.exclude(sender=request.user).exclude(read_by=request.user).count()
        
        rooms_data.append({
            'room': room,
            'display_name': display_name,
            'unread_count': unread_count
        })
        
    # 2. Собираем списки пользователей для модалки создания нового чата
    all_users = User.objects.exclude(id=request.user.id).order_by('last_name')
    staff_users = all_users.filter(Q(is_staff=True) | Q(groups__name__in=['Бухгалтер', 'Преподаватель'])).distinct()
    parent_users = all_users.filter(groups__name='Родитель')

    return render(request, 'dashboard_admin/chat_list.html', {
        'rooms_data': rooms_data,
        'staff_users': staff_users,
        'parent_users': parent_users,
        'base_template': 'dashboard_admin/base_admin.html'
    })


@login_required
@user_passes_test(is_admin)
@require_POST
def admin_chat_create(request):
    chat_type = request.POST.get('chat_type')  # 'private' или 'group'
    name = request.POST.get('name', '').strip()
    selected_user_ids = request.POST.getlist('participants')

    if not selected_user_ids:
        messages.error(request, 'Ошибка: Вы не выбрали ни одного участника для беседы.')
        return redirect('dashboard_admin:chat_list')

    # Переводим ID в объекты пользователей
    selected_users = list(User.objects.filter(id__in=selected_user_ids))

    if chat_type == 'private':
        # Твоя железная логика для ЛИЧНЫХ ЧАТОВ
        other = selected_users[0] if selected_users else None
        if other:
            # Ищем существующий приватный чат между админом и этим пользователем
            existing = ChatRoom.objects.filter(
                room_type='private',
                participants=request.user
            ).filter(participants=other).distinct().first()
            
            if existing:
                # Если админ ранее скрыл этот чат для себя — убираем из deleted_for
                if existing.deleted_for.filter(id=request.user.id).exists():
                    existing.deleted_for.remove(request.user)
                return redirect('chat:chat_detail', room_id=existing.id)
            
            # Если чата не было — создаем строго по твоей схеме
            room = ChatRoom.objects.create(room_type='private', created_by=request.user)
            room.participants.add(request.user, other)
            messages.success(request, f'Чат с пользователем успешно инициализирован.')
            return redirect('chat:chat_detail', room_id=room.id)
            
    elif chat_type == 'group':
        # Твоя логика для ГРУППОВЫХ ЧАТОВ
        if not name:
            messages.error(request, 'Ошибка: Укажите название группового чата.')
            return redirect('dashboard_admin:chat_list')
            
        # Проверяем, нет ли уже группы с таким же названием у админа
        existing = ChatRoom.objects.filter(
            room_type='group',
            name=name,
            participants=request.user
        ).first()
        
        if existing:
            return redirect('chat:chat_detail', room_id=existing.id)
            
        # Создаем групповой чат
        room = ChatRoom.objects.create(room_type='group', name=name, created_by=request.user)
        # Добавляем выбранных людей + самого админа
        room.participants.set(selected_users + [request.user])
        messages.success(request, f'Групповой канал "{name}" успешно запущен.')
        return redirect('chat:chat_detail', room_id=room.id)

    return redirect('dashboard_admin:chat_list')
