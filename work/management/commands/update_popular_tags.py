# -*- coding: utf-8 -*-
from django.core.management.base import BaseCommand

from work.tasks import update_popular_tags


class Command(BaseCommand):
    help = 'Update vacancies for all existed tags in the database'

    def handle(self, *args, **options):
        update_popular_tags()
