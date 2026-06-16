from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from main.models import Course
from django import forms

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
