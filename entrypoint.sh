#!/bin/sh
set -e

echo "==> Django veritabanı geçişleri uygulanıyor..."
python manage.py migrate --noinput

echo "==> Statik dosyalar toplanıyor..."
python manage.py collectstatic --noinput

echo "==> Yönetici (superuser) kontrol ediliyor..."
python manage.py init_admin

echo "==> Sunucu başlatılıyor: $@"
exec "$@"
