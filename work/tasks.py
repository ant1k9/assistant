# -*- coding: utf-8 -*-
import requests

from django.db.models import Count
from django.conf import settings

from .models import (
    Vacancy, Tag, VacancyTag,
)

from .update import (
    VacancyLoader,
)


def __get_exchange_rate(base: str):
    response = requests.get(settings.EXCHANGE_RATE_URL).json()
    return response['Valute'][base]['Value']


def update_foreign_currency_salaries():
    """
    Piece of documentation
    """
    for currency_t in [('EUR', '€'), ('USD', '$')]:
        rate = __get_exchange_rate(currency_t[0])
        for currency in currency_t:
            for vacancy in Vacancy.objects.filter(currency__icontains=currency):
                if vacancy.salary_from is not None:
                    vacancy.salary_from *= rate
                if vacancy.salary_to is not None:
                    vacancy.salary_to *= rate
                vacancy.currency = 'RUR'
                vacancy.save()


def update_popular_tags():
    loader = VacancyLoader()
    for tag_value in VacancyTag.objects.values('tag__value') \
                                       .annotate(count=Count('tag__value')) \
                                       .order_by('-count') \
                                       .values_list('tag__value', flat=True)[:15]:
        loader.update_by_tag(tag_value)
    update_foreign_currency_salaries()
