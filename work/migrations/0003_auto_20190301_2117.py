# Generated by Django 2.1.2 on 2019-03-01 21:17

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('work', '0002_auto_20190301_2052'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tag',
            name='value',
            field=models.CharField(max_length=64, unique=True, verbose_name='Tag'),
        ),
    ]
