# -*- coding: utf-8 -*-
import re

from datetime import datetime
from http import HTTPStatus
from typing import List
from urllib.parse import quote

import requests

from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from lxml.etree import fromstring

from .models import (
    Tag,
    Vacancy,
    VacancyTag,
)

############################################################
## Regular Expressions
############################################################

RE_VACANCY_AND_SALARY = re.compile(
    r'[^«]*«(?P<vacancy>[^»]*)»\s*(\((?P<salary_text>[^)]*)\))?'
)

RE_CITY = re.compile(
    '(?P<city>[^,]+)'
)

RE_SALARY = re.compile(
    r'.*?(?=от|до)'
    r'\s*(?P<salary_from>от (?P<bottom_salary>[\d\s]+))?'
    r'\s*(?P<salary_to>до (?P<top_salary>[\d\s]+))?'
    r'\s*(?P<currency>[^.]+)?'
)

RE_TAG = r'(\b|.*\W){tag}(\b|\W.*)'

############################################################
## Main Loader for vacancies updates
############################################################

class VacancyLoader:

    def __load_hh(self, data: List[dict], tag: str) -> None:
        if not Tag.objects.filter(value=tag):
            Tag.objects.create(value=tag)

        tag_item = Tag.objects.get(value=tag)

        for item in data:
            vacancy = dict(
                apply_url=item.get('alternate_url'),
                currency=item['salary'].get('currency') if item.get('salary') else None,
                employer=item['employer'].get('name') if item.get('employer') else None,
                has_test=item.get('has_test'),
                hh_id=item.get('id'),
                published_at=parse_datetime(item.get('published_at')),
                requirements=(item['snippet'].get('requirement') or '')
                                             .replace('highlighttext', 'b'),
                responsibility=(item['snippet'].get('responsibility') or '')
                                               .replace('highlighttext', 'b'),
                salary_from=item['salary'].get('from') if item.get('salary') else None,
                salary_to=item['salary'].get('to') if item.get('salary') else None,
                source='hh',
                subway=item['address']['metro'].get('station_name')
                    if item.get('address') and item['address'].get('metro') else None,
                url=item.get('url'),
                vacancy=item.get('name'),
            )

            if vacancy['hh_id']:
                vacancy_items = Vacancy.objects.filter(hh_id=vacancy['hh_id'])
                if not vacancy_items:
                    vacancy_item = Vacancy.objects.create(**vacancy)
                    VacancyTag.objects.create(tag=tag_item, vacancy=vacancy_item)
                else:
                    vacancy_item = vacancy_items[0]
                    vacancy.pop('hh_id')
                    for attr, value in vacancy.items():
                        if value != getattr(vacancy_item, attr):
                            setattr(vacancy_item, attr, value)
                    vacancy_item.save()
                    VacancyTag.objects.get_or_create(tag=tag_item, vacancy=vacancy_item)

    def __load_your_gms(self, data: List[dict], tag: str) -> None:
        if not Tag.objects.filter(value=tag):
            Tag.objects.create(value=tag)

        tag_item = Tag.objects.get(value=tag)

        def _rehash(_hash: str) -> int:
            result = 0
            for ch in _hash:
                result += (ord(ch) + result * 331) % 1_000_000_000
            return result

        for item in data:
            if tag.lower() not in [t.lower() for t in item['stack']]:
                continue

            vacancy = dict(
                apply_url=f'https://your.gms.tech/v/{item["id"]}',
                currency=item.get('salary_currency'),
                employer=item['company'].get('name') if item.get('company') else None,
                hh_id=_rehash(item.get('id')),
                published_at=parse_date(item.get('published_at')),
                requirements=item.get('offer_description'),
                salary_from=item.get('salary_display_from'),
                salary_to=item.get('salary_display_to'),
                source='gms',
                url=f'https://your.gms.tech/v/{item["id"]}',
                vacancy=item.get('position'),
            )

            if vacancy['hh_id']:
                vacancy_item = Vacancy.objects.filter(hh_id=vacancy['hh_id']).first()
                if not vacancy_item:
                    vacancy_item = Vacancy.objects.create(**vacancy)
                    VacancyTag.objects.create(tag=tag_item, vacancy=vacancy_item)
                else:
                    vacancy.pop('hh_id')
                    for attr, value in vacancy.items():
                        if value != getattr(vacancy_item, attr):
                            setattr(vacancy_item, attr, value)
                    vacancy_item.save()
                    VacancyTag.objects.get_or_create(tag=tag_item, vacancy=vacancy_item)

    def __load_moi_krug_and_return_are_outdated(self, text: str, tag: str, from_date: datetime) \
            -> bool:
        if not Tag.objects.filter(value=tag):
            Tag.objects.create(value=tag)

        tag_item = Tag.objects.get(value=tag)
        tree = fromstring(text.encode('utf-8'))

        for item in tree.findall('.//item'):
            title = item.find('title').text
            city, bottom_salary, top_salary, currency = '', None, None, None

            match = re.match(RE_VACANCY_AND_SALARY, title)
            if not match:
                continue

            vacancy, salary_text = match.group('vacancy'), match.group('salary_text') or ''

            if not salary_text.startswith('от') or salary_text.startswith('до'):
                match = re.match(RE_CITY, salary_text)
                city = match.group('city') if match else ''

            match = re.match(RE_SALARY, salary_text)
            if match:
                bottom_salary = match.group('bottom_salary')
                top_salary = match.group('top_salary')
                currency = match.group('currency')

            if self.__is_match(tag, vacancy, city):
                vacancy = dict(
                    apply_url=item.find('link').text,
                    currency=currency,
                    employer=item.find('author').text,
                    hh_id=item.find('guid').text,
                    published_at=datetime.strptime(
                        item.find('pubDate').text, '%a, %d %b %Y %H:%M:%S %z'),
                    requirements=item.find('description').text,
                    salary_from=bottom_salary.replace(' ', '') if bottom_salary else None,
                    salary_to=top_salary.replace(' ', '') if top_salary else None,
                    source='moi_krug',
                    url=item.find('link').text,
                    vacancy=vacancy
                )
                if vacancy['published_at'] < from_date:
                    return True
                if vacancy['hh_id']:
                    vacancy_items = Vacancy.objects.filter(hh_id=vacancy['hh_id'])
                    vacancy_item = Vacancy.objects.create(**vacancy) if not vacancy_items \
                            else vacancy_items[0]
                    VacancyTag.objects.get_or_create(tag=tag_item, vacancy=vacancy_item)

        return False

    @staticmethod
    def __is_match(tag: str, vacancy: str, city: str) -> bool:
        tag_pattern = RE_TAG.format(tag=re.escape(tag.lower()))
        vacancy = vacancy.lower()

        if tag.lower() == 'go':
            go_tag_pattern = RE_TAG.format(tag=re.escape(tag.lower() + 'lang'))
            if (
                re.match(tag_pattern, vacancy, re.IGNORECASE) is None
                and re.match(go_tag_pattern, vacancy, re.IGNORECASE) is None
            ):
                return False
        elif re.match(tag_pattern, vacancy, re.IGNORECASE) is None:
            return False

        return city == '' or city.lower() == 'москва'

    def update_by_tag(self, tag: str) -> None:
        last_update_date = timezone.now() - timezone.timedelta(days=7)
        has_answers = True
        max_queries = 10
        while has_answers and max_queries > 0:
            hh_url = settings.HH_API_URL.format(
                date_from=last_update_date.strftime('%Y-%m-%d'),
                tag=quote(tag), page=10 - max_queries
            )
            max_queries -= 1
            response = requests.get(hh_url)
            if response.status_code == HTTPStatus.OK.value:
                json_data = response.json()
                if json_data['page'] == json_data['pages'] - 1:
                    has_answers = False
                self.__load_hh(json_data['items'], tag)
            else:
                has_answers = False

        max_queries = 10
        while max_queries > 0:
            max_queries -= 1
            response = requests.get(settings.MOI_KRUG_URL.format(page=10 - max_queries))
            if (
                response.status_code != HTTPStatus.OK.value
                or self.__load_moi_krug_and_return_are_outdated(
                    response.text, tag, last_update_date
                )
            ):
                break

        response = requests.get(settings.YOUR_GMS_TECH_URL)
        if response.status_code == HTTPStatus.OK.value:
            json_data = response.json()
            self.__load_your_gms(json_data['offers'], tag)
