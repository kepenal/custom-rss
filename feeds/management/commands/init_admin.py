import os
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

class Command(BaseCommand):
    help = 'Ortam değişkenlerine göre idempotent superuser oluşturur.'

    def handle(self, *args, **options):
        username = os.getenv('DJANGO_SUPERUSER_USERNAME')
        password = os.getenv('DJANGO_SUPERUSER_PASSWORD')
        email = os.getenv('DJANGO_SUPERUSER_EMAIL', 'admin@example.com')

        if not username or not password:
            self.stdout.write(self.style.WARNING('DJANGO_SUPERUSER_USERNAME veya DJANGO_SUPERUSER_PASSWORD tanımlanmamış, superuser oluşturma atlandı.'))
            return

        User = get_user_model()
        user = User.objects.filter(username=username).first()
        if user:
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' zaten mevcut."))
            if not user.is_superuser or not user.is_staff:
                user.is_superuser = True
                user.is_staff = True
                user.save()
        else:
            User.objects.create_superuser(username=username, email=email, password=password)
            self.stdout.write(self.style.SUCCESS(f"Superuser '{username}' başarıyla oluşturuldu."))
