from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import Profile, Child
from django.contrib.auth.models import Group


class UserRegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Электронная почта")
    phone = forms.CharField(max_length=20, label="Контактный телефон")
    license_accepted = forms.BooleanField(
        required=True, label="Я принимаю Лицензионное соглашение"
    )
    consent_given = forms.BooleanField(
        required=True, label="Я даю согласие на обработку персональных данных"
    )

    class Meta:
        model = User
        fields = ("email", "password1", "password2")

    # username не включаем

    def save(self, commit=True):
        user = super().save(commit=False)
        # Генерируем username из email (до @)
        user.username = self.cleaned_data["email"].split("@")[0]
        # Убедимся, что username уникален
        if User.objects.filter(username=user.username).exists():
            user.username = f"{user.username}_{User.objects.count()}"
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
            Profile.objects.create(
                user=user,
                phone=self.cleaned_data["phone"],
                license_accepted=self.cleaned_data["license_accepted"],
                consent_given=self.cleaned_data["consent_given"],
            )
        #Добавляем user в группу "Родитель"
        parent_group = Group.objects.get(name='Родитель')
        user.groups.add(parent_group)    
        return user

    def clean_email(self):
        email = self.cleaned_data.get("email")
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError(
                "Пользователь с таким email уже зарегистрирован."
            )
        return email


class EmailAuthenticationForm(AuthenticationForm):
    username = forms.EmailField(
        label="Электронная почта",
        widget=forms.EmailInput(attrs={"class": "form-control"}),
    )
    password = forms.CharField(
        label="Пароль", widget=forms.PasswordInput(attrs={"class": "form-control"})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Электронная почта"


class ProfileForm(forms.ModelForm):
    first_name = forms.CharField(max_length=30, required=True, label='Имя')
    last_name = forms.CharField(max_length=30, required=True, label='Фамилия')
    
    class Meta:
        model = Profile
        fields = ['middle_name', 'phone', 'birth_date', 'gender']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name

    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        if commit:
            user.save()
            profile.save()
        return profile

class ChildForm(forms.ModelForm):
    class Meta:
        model = Child
        fields = ['last_name', 'first_name', 'middle_name', 'birth_date', 'gender']
        widgets = {
            'birth_date': forms.DateInput(attrs={'type': 'date'}),
        }
