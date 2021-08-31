from django.urls import path

from .views import (
    VacancyView, add_tag, get_hh_description,
    get_moi_krug_description, delete_usertag,
)

urlpatterns = [
    path('add_tag', add_tag, name='add_tag'),
    path('delete_usertag', delete_usertag, name='delete_usertag'),
    path('hh_description', get_hh_description, name='hh_description'),
    path('moi_krug_description', get_moi_krug_description, name='moi_krug_description'),
    path('', VacancyView.as_view(), name='work'),
]
