from django import forms
from django.contrib.auth import get_user_model
from .models import ChatRoom

User = get_user_model()

class CreateChatForm(forms.Form):
    CHAT_TYPES = (
        ('group', 'Групповой чат'),
        ('private', 'Личный чат'),
    )
    chat_type = forms.ChoiceField(choices=CHAT_TYPES, widget=forms.RadioSelect, initial='private')
    name = forms.CharField(max_length=255, required=False, label='Название чата (для группового)')
    participants = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
        required=True,
        label='Участники'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        self.user = user
        if not user:
            return

        from teacher.models import Group, GroupMember
        from accounts.models import Child

        if user.groups.filter(name='Преподаватель').exists():
            # Преподаватель: показываем родителей учеников ЕГО групп
            
            # 1. Получаем чистый список ID всех детей, зачисленных в группы этого учителя
            child_ids = GroupMember.objects.filter(
                group__teacher=user
            ).values_list('child_id', flat=True).distinct()
            
            # 2. Достаем этих детей по их ID
            children = Child.objects.filter(id__in=child_ids)
            
            # 3. Находим родителей этих детей
            participants_qs = User.objects.filter(children__in=children).distinct()
            
        else:
            # Родитель: показываем преподавателей и других родителей из тех же групп
            children = user.children.all()
            
            # Находим чистые ID групп, в которых учатся дети этого родителя
            group_ids = GroupMember.objects.filter(
                child__in=children
            ).values_list('group_id', flat=True).distinct()
            
            # Преподаватели этих групп
            teachers = User.objects.filter(teaching_groups__id__in=group_ids).distinct()
            
            # Другие родители (чьи дети учатся в тех же ID групп)
            other_parents = User.objects.filter(
                children__id__in=Child.objects.filter(
                    id__in=GroupMember.objects.filter(group_id__in=group_ids).values_list('child_id', flat=True)
                )
            ).exclude(id=user.id).distinct()
            
            participants_qs = (teachers | other_parents).distinct()

        # Назначаем отфильтрованную выборку в поле формы
        self.fields['participants'].queryset = participants_qs

        # --- ЖЕЛЕЗНОЕ ИСПРАВЛЕНИЕ ОТОБРАЖЕНИЯ ИМЕН ---
        # Переопределяем функцию генерации текста метки для каждого чекбокса юзера
        self.fields['participants'].label_from_instance = lambda obj: (
            f"{obj.last_name} {obj.first_name}".strip() or obj.username
        )

    def clean(self):
        cleaned_data = super().clean()
        chat_type = cleaned_data.get('chat_type')
        name = cleaned_data.get('name')
        participants = cleaned_data.get('participants')

        if chat_type == 'group' and not name:
            self.add_error('name', 'Для группового чата обязательно название')
        
        # Защита от пустого значения или неверного выбора в приватном чате
        if chat_type == 'private' and participants:
            if len(participants) != 1:
                self.add_error('participants', 'В личном чате должен быть ровно один участник')
                
        return cleaned_data