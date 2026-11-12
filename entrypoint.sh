#!/bin/sh
set -e

ENV_MODE="${ENVIRONMENT:-${DJANGO_ENV:-production}}"
echo "==> Mod: $ENV_MODE"

echo "==> Veritabanı geçişleri kontrol ediliyor / uygulanıyor..."
python manage.py migrate --noinput

# Production veya statik toplama istendiğinde collectstatic otomatik koşulur
if [ "$ENV_MODE" != "development" ] && [ "$ENV_MODE" != "dev" ]; then
  echo "==> [Production] Statik dosyalar toplanıyor (collectstatic)..."
  python manage.py collectstatic --noinput
else
  echo "==> [Development] Canlı geliştirme modu aktif (collectstatic atlandı)."
fi

echo "==> Yönetici (superuser) kontrol ediliyor..."
python manage.py init_admin

echo "==> Servis başlatılıyor: $@"
exec "$@"
