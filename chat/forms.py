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
            # Преподаватель: показываем родителей учеников его групп
            # Находим всех детей, которые учатся в группах этого преподавателя
            groups = Group.objects.filter(teacher=user)
            children = Child.objects.filter(groups__in=groups).distinct()
            # Родители этих детей
            participants_qs = User.objects.filter(children__in=children).distinct()
        else:
            # Родитель: показываем преподавателей и других родителей из тех же групп
            # Группы, в которых участвуют дети этого родителя
            children = user.children.all()
            group_ids = GroupMember.objects.filter(child__in=children).values_list('group_id', flat=True).distinct()
            # Преподаватели этих групп
            teachers = User.objects.filter(teaching_groups__id__in=group_ids).distinct()
            # Другие родители (чьи дети учатся в тех же группах)
            other_parents = User.objects.filter(children__groups__id__in=group_ids).exclude(id=user.id).distinct()
            participants_qs = (teachers | other_parents).distinct()

        self.fields['participants'].queryset = participants_qs

    def clean(self):
        cleaned_data = super().clean()
        chat_type = cleaned_data.get('chat_type')
        name = cleaned_data.get('name')
        participants = cleaned_data.get('participants')

        if chat_type == 'group' and not name:
            self.add_error('name', 'Для группового чата обязательно название')
        if chat_type == 'private' and len(participants) != 1:
            self.add_error('participants', 'В личном чате должен быть ровно один участник')
        return cleaned_data