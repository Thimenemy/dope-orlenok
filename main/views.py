from django.shortcuts import render, redirect
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from .models import Course


def home(request):
    if request.user.is_authenticated:
        # =========================================================================
        # ЖЕСТКИЙ ПЕРЕХОД ДЛЯ АДМИНИСТРАТОРА СИСТЕМЫ
        # =========================================================================
        if request.user.is_staff and request.user.is_superuser:
            return redirect("dashboard_admin:course_list")

        # Твои стандартные роли
        elif request.user.groups.filter(name="Бухгалтер").exists():
            return redirect("accountant:enrollment_list")
        elif request.user.groups.filter(name="Преподаватель").exists():
            return redirect("teacher:group_list")
        else:
            return redirect("home:dashboard")
    else:
        return course_list(request)


def course_list(request):
    # Берём только доступные курсы
    courses = Course.objects.filter(available=True)
    base_template = (
        "home/base_auth.html" if request.user.is_authenticated else "base.html"
    )
    # Пагинация: 3 курса на странице
    paginator = Paginator(courses, 3)
    page = request.GET.get("page")
    try:
        courses_page = paginator.page(page)
    except PageNotAnInteger:
        courses_page = paginator.page(1)
    except EmptyPage:
        courses_page = paginator.page(paginator.num_pages)

    context = {
        "courses": courses_page,
        "base_template": base_template,
        "paginator": paginator,
        "page_obj": courses_page,
        "is_paginated": courses_page.has_other_pages(),
    }
    return render(request, "list.html", context)
