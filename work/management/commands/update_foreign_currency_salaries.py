# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from work.tasks import update_foreign_currency_salaries


class Command(BaseCommand):
    help = 'Recalculate currency for vacancies in Euro and Dollars'

    def handle(self, *args, **options):
        update_foreign_currency_salaries()
