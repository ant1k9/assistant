from datetime import timedelta, datetime

from django.contrib.auth import get_user_model
from django.db import models
from django.utils import timezone

User = get_user_model()

############################################################
## Constants
############################################################

FIELD_CHOICES = (
    (1, "vacancy"),
    (2, "requirements"),
    (3, "description"),
)

SOURCE_CHOICES = (
    ('hh', 'HeadHunter'),
    ('moi_krug', 'Мой Круг'),
)

############################################################
## HeadHunter API Model
############################################################

class Description(models.Model):
    text = models.TextField()
    vacancy = models.OneToOneField('Vacancy', verbose_name='Vacancy', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.vacancy}'


class Tag(models.Model):
    value = models.CharField('Tag', max_length=64, unique=True)

    def __str__(self):
        return self.value


class UserTag(models.Model):
    tag = models.ForeignKey(Tag, verbose_name='Tag', on_delete=models.CASCADE)
    user = models.ForeignKey(User, verbose_name='User', on_delete=models.CASCADE)

    class Meta:
        unique_together = ('user', 'tag')

    def __str__(self):
        return f'{self.tag} for {self.user.username}'


class Vacancy(models.Model):
    apply_url = models.CharField('Apply URL', max_length=128, null=True)
    currency = models.CharField('Currency', max_length=32, default='RUR', null=True)
    employer = models.CharField('Employer', max_length=256)
    has_test = models.BooleanField('Has Test', null=True)
    hh_id = models.BigIntegerField('HH id', unique=True)
    published_at = models.DateTimeField('Published at')
    requirements = models.TextField('Requirements')
    responsibility = models.TextField('Responsibilities', null=True)
    salary_from = models.FloatField('Salary From', null=True)
    salary_to = models.FloatField('Salary To', null=True)
    source = models.CharField('Source', max_length=32, choices=SOURCE_CHOICES, default='hh')
    subway = models.CharField('Subway', max_length=64, null=True)
    url = models.CharField('URL', max_length=128, null=True)
    vacancy = models.CharField('Vacancy', max_length=128)

    class Meta:
        ordering = ('-published_at',)

    def __str__(self):
        return self.vacancy

    @classmethod
    def last_update_date(cls, tag: str) -> datetime:
        tag_item = Tag.objects.filter(value=tag)
        if tag_item:
            tag_item = tag_item[0]
            vacancies = cls.objects.prefetch_related('vacancytag_set') \
                                   .filter(vacancytag__tag=tag_item)
            if vacancies:
                return vacancies.values_list('published_at', flat=True) \
                                .order_by('-published_at')[0]
        return timezone.now() - timedelta(days=7)


class VacancyTag(models.Model):
    tag = models.ForeignKey('Tag', verbose_name='Tag', on_delete=models.CASCADE)
    vacancy = models.ForeignKey('Vacancy', verbose_name='Vacancy', on_delete=models.CASCADE)

    def __str__(self):
        return f'{self.tag} -- {self.vacancy}'
