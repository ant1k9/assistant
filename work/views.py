# -*- coding: utf-8 -*-
import requests

from bs4 import BeautifulSoup
from datetime import timedelta, datetime
from itertools import groupby
from typing import Tuple, Dict
from urllib.parse import unquote

from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm, UserCreationForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.db import IntegrityError, models
from django.db.models.functions import TruncWeek
from django.shortcuts import render, redirect, reverse, HttpResponse
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View, generic

from .models import (
    Description, Tag, Vacancy, UserTag,
)

from .update import (
    VacancyLoader,
)

############################################################
## Views
############################################################

class LoginView(LoginView):
    template_name = 'login.html'
    redirect_field_name = 'next'
    authentication_form = AuthenticationForm
    redirect_authenticated_user = True


class SignUpView(generic.CreateView):
    form_class = UserCreationForm
    success_url = reverse_lazy('login')
    template_name = 'signup.html'


def do_logout(request):
    logout(request)
    return redirect(reverse('login'))


def unpack_query_params(request) -> Dict[str, str]:
    return dict(
        map(
            lambda query: tuple(query.split('=', 1)),
            filter(
                lambda query: query,
                unquote(request.environ['QUERY_STRING']).split('&')
            )
        )
    )


class VacancyView(LoginRequiredMixin, View):
    login_url = reverse_lazy('login')
    redirect_field_name = 'redirect_to'

    def __retrieve_days_and_hours(self, days_hours_ago: str) -> Tuple[int, int]:
        parts = list(filter(lambda part: part, days_hours_ago.replace('+', ' ').split(' ')))

        days_list = list(filter(lambda part: part.endswith('d'), parts))
        days = int(days_list[0].strip('d')) if days_list else 0

        hours_list = list(filter(lambda part: part.endswith('h'), parts))
        hours = int(hours_list[0].strip('h')) if hours_list else 0

        return days, hours

    def get(self, request):
        query_params = unpack_query_params(request)

        days_hours_ago = query_params.get('days_hours_ago', '30d')
        days, hours = self.__retrieve_days_and_hours(days_hours_ago)
        date_from = timezone.now() - timedelta(days=days, hours=hours)

        salary_from = int(query_params.get('salary_from') or '0')
        salary_to = int(query_params.get('salary_to') or '0')

        tags = query_params.get('tags', '').split(',')
        page = int(query_params.get('page', '1'))
        tags_instances = Tag.objects.filter(value__in=tags)

        user_tags_ids = UserTag.objects.filter(user=request.user) \
                                       .values_list('tag_id', flat=True)

        employers = Vacancy.objects.filter(vacancytag__tag__in=user_tags_ids) \
                                   .values_list('employer', flat=True) \
                                   .annotate(cnt=models.Count('employer')) \
                                   .order_by('-cnt')[:10]

        vacancies = Vacancy.objects.prefetch_related('vacancytag_set__tag')
        if salary_from:
            vacancies = vacancies.filter(salary_from__gte=salary_from)
        if salary_to:
            vacancies = vacancies.filter(salary_to__gte=salary_to)

        employer = unquote(query_params.get('employer', ''))
        tags_items = Tag.objects.filter(id__in=user_tags_ids) \
                                .values_list('value', flat=True)

        if employer:
            vacancies = vacancies.filter(employer=employer) \
                                 .filter(vacancytag__tag_id__in=user_tags_ids)
        else:
            vacancies = vacancies.filter(vacancytag__tag__in=tags_instances)

        average_salary_from = vacancies.values('salary_from') \
                                       .aggregate(avg=models.Avg('salary_from'))['avg']
        average_salary_to = vacancies.values('salary_to') \
                                     .aggregate(avg=models.Avg('salary_to'))['avg']

        average_salary_from_by_month = self.__group_by_date(
                vacancies.annotate(week=TruncWeek('published_at'))
                         .exclude(salary_from=None)
                         .values_list('week', 'salary_from')
                         .order_by('week')
        )

        average_salary_to_by_month =  self.__group_by_date(
                vacancies.annotate(week=TruncWeek('published_at'))
                         .exclude(salary_to=None)
                         .values_list('week', 'salary_to')
                         .order_by('week')
        )

        if not employer:
            vacancies = vacancies.filter(
                published_at__gte=date_from)[(10 * (page - 1)):(10 * page)]

        return render(request, 'index.html', context={
            'average_salary_from': average_salary_from,
            'average_salary_from_by_month': average_salary_from_by_month,
            'average_salary_to': average_salary_to,
            'average_salary_to_by_month': average_salary_to_by_month,
            'vacancies': vacancies,
            'salary_from': salary_from,
            'salary_to': salary_to,
            'tags': ','.join(tags),
            'days_hours_ago': f'{days}d {hours}h',
            'tags_items': tags_items,
            'employers': employers,
            'page': page,
        })

    def __group_by_date(self, queryset: models.QuerySet) -> Dict[datetime, float]:
        collection = {}
        for key, value in groupby(list(queryset), lambda pair: pair[0]):
            _list_value = list(map(lambda item: item[1], value))
            collection[key.strftime('%Y-%m-%d')] = round(
                sum(_list_value) / len(_list_value), 1
            ) if _list_value else None
        return collection


@login_required
def add_tag(request):
    new_tag = request.GET.get('new_tag')
    if new_tag and not Tag.objects.filter(value=new_tag):
        try:
            Tag.objects.create(value=new_tag)
        except IntegrityError:
            return redirect(reverse('work'))

    if new_tag:
        tag = Tag.objects.get(value=new_tag)
        UserTag.objects.update_or_create(user=request.user, tag=tag)
        loader = VacancyLoader()
        loader.update_by_tag(new_tag)

    return redirect(f'{reverse("work")}?tags={new_tag}')


@login_required
def delete_usertag(request):
    query_params = unpack_query_params(request)
    if query_params.get('tag') and query_params.get('user_id'):
        UserTag.objects.filter(tag__value=query_params['tag'], user_id=query_params['user_id']) \
                       .delete()

    return redirect(reverse('work'))


@login_required
def get_hh_description(request):
    hh_id = request.GET.get('hh_id')
    vacancy = Vacancy.objects.filter(hh_id=hh_id)

    if vacancy:
        vacancy = vacancy[0]
        description = Description.objects.filter(vacancy=vacancy)
        if not description:
            data = requests.get(vacancy.url).json()
            description = Description.objects.create(
                text=data['description'], vacancy=vacancy
            )
        else:
            description = description[0]
        return HttpResponse(description.text)

    return HttpResponse('')


@login_required
def get_moi_krug_description(request):
    hh_id = request.GET.get('hh_id')
    vacancy = Vacancy.objects.filter(hh_id=hh_id)

    if vacancy:
        vacancy = vacancy[0]
        description = Description.objects.filter(vacancy=vacancy)
        if not description:
            data = requests.get(vacancy.url).text
            soup = BeautifulSoup(data, 'lxml')
            text = repr(soup.find('div', {'class': 'job_show_description'}))
            description = Description.objects.create(
                text=text, vacancy=vacancy
            )
        else:
            description = description[0]
        return HttpResponse(description.text)

    return HttpResponse('')
