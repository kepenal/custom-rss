#!/bin/sh
set -e

ENV_MODE="${ENVIRONMENT:-${DJANGO_ENV:-production}}"
echo "==> Mod: $ENV_MODE"

echo "==> Veritabanı geçişleri kontrol ediliyor / uygulanıyor..."
python manage.py migrate --noinput

echo "==> Statik dosyalar toplanıyor (collectstatic)..."
python manage.py collectstatic --noinput

echo "==> Yönetici (superuser) kontrol ediliyor..."
python manage.py init_admin

echo "==> Servis başlatılıyor: $@"
exec "$@"
