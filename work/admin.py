from django.contrib import admin

from .models import (
   Description, Tag, Vacancy, VacancyTag,
)

@admin.register(Description)
class DescriptionAdmin(admin.ModelAdmin):
    pass


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    pass


@admin.register(Vacancy)
class VacancyAdmin(admin.ModelAdmin):
    list_filter = ['source', 'employer']


@admin.register(VacancyTag)
class VacancyTagAdmin(admin.ModelAdmin):
    pass
