import re
import secrets
import hashlib
from unicodedata import normalize
from django.utils.text import slugify

TURKISH_CHAR_MAP = {
    'ı': 'i', 'İ': 'i', 'I': 'i',
    'ğ': 'g', 'Ğ': 'g',
    'ü': 'u', 'Ü': 'u',
    'ş': 's', 'Ş': 's',
    'ö': 'o', 'Ö': 'o',
    'ç': 'c', 'Ç': 'c',
}

def normalize_channel_slug(text: str) -> str:
    if not text:
        return ''
    text = text.strip()
    for tr_char, eng_char in TURKISH_CHAR_MAP.items():
        text = text.replace(tr_char, eng_char)
    text = slugify(text)
    text = re.sub(r'[^a-z0-9_-]', '', text.lower())
    return text

def hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.strip().encode('utf-8')).hexdigest()

def generate_api_key(prefix: str = 'crss') -> tuple[str, str, str]:
    random_part = secrets.token_urlsafe(32)
    raw_key = f"{prefix}_{random_part}"
    key_hash = hash_token(raw_key)
    key_prefix = raw_key[:8]
    return raw_key, key_hash, key_prefix
