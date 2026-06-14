from django import forms
from .models import Group
from accounts.models import Child
from main.models import Course

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'course', 'start_date', 'end_date', 'max_students']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'end_date': forms.DateInput(attrs={'type': 'date'}),
        }

class AddStudentForm(forms.Form):
    child = forms.ModelChoiceField(queryset=Child.objects.none(), label='Ученик')
    # Поля для фильтрации (необязательные, но можно добавить)
    course_filter = forms.ModelChoiceField(queryset=None, required=False, label='Фильтр по курсу')
    name_filter = forms.CharField(required=False, label='Имя или фамилия')

    def __init__(self, *args, **kwargs):
        group = kwargs.pop('group', None)
        super().__init__(*args, **kwargs)
        if group:
            paid_children = Child.objects.filter(
                enrollments__course=group.course,
                enrollments__status='paid'
            ).exclude(
                id__in=group.members.values_list('child_id', flat=True)
            ).distinct()
            self.fields['child'].queryset = paid_children.order_by('last_name', 'first_name')
            self.fields['course_filter'].queryset = Course.objects.all()

class ScheduleForm(forms.Form):
    weekdays = forms.MultipleChoiceField(
        choices=[
            ('mon', 'Пн'), ('tue', 'Вт'), ('wed', 'Ср'),
            ('thu', 'Чт'), ('fri', 'Пт'), ('sat', 'Сб'), ('sun', 'Вс')
        ],
        widget=forms.CheckboxSelectMultiple,
        label='Дни недели'
    )
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='Время начала')
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='Время окончания')