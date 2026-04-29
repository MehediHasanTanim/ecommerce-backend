from django.apps import AppConfig

class $(echo $app | sed -r 's/(^|_)([a-z])/\U\2/g')Config(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.$app'
