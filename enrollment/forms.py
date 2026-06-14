from django import forms
from .models import Enrollment
from accounts.models import Child


class EnrollmentFullForm(forms.Form):
    child_id = forms.ModelChoiceField(
        queryset=Child.objects.none(),
        empty_label="-- Выберите ребёнка --",
        widget=forms.Select(attrs={'class': 'form-select form-select-lg'})
    )
    additional_info = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )
    parent_passport = forms.FileField(
        required=True,
        label="Паспорт родителя",
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    child_snils = forms.FileField(
        required=True,
        label="СНИЛС ребёнка",
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    child_birth_cert = forms.FileField(
        required=True,
        label="Свидетельство о рождении",
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    consent = forms.BooleanField(
        required=True,
        label="Согласие",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user:
            self.fields['child_id'].queryset = Child.objects.filter(parent=user)



class EnrollmentForm(forms.ModelForm):
    class Meta:
        model = Enrollment
        fields = [
            'parent_last_name', 'parent_first_name', 'parent_middle_name',
            'child_last_name', 'child_first_name', 'child_middle_name',
            'child_birth_date', 'additional_info',
        ]
        widgets = {
            'child_birth_date': forms.DateInput(attrs={'type': 'date'}),
            'additional_info': forms.Textarea(attrs={'rows': 3}),
        }
        labels = {
            'parent_last_name': 'Фамилия родителя',
            'parent_first_name': 'Имя родителя',
            'parent_middle_name': 'Отчество родителя',
            'child_last_name': 'Фамилия ребёнка',
            'child_first_name': 'Имя ребёнка',
            'child_middle_name': 'Отчество ребёнка',
            'child_birth_date': 'Дата рождения ребёнка',
            'additional_info': 'Доп. информация о ребёнке (аллергии, особенности)',
        }
