from django.conf import settings
from django.utils import timezone
from .models import ApiKey
from .utils import hash_token

def extract_token_from_request(request, allow_query_param: bool = False) -> str:
    auth_header = request.headers.get('Authorization', '').strip()
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip()
    
    api_key_header = request.headers.get('X-API-Key', '').strip()
    if api_key_header:
        return api_key_header
        
    if allow_query_param:
        query_key = request.GET.get('key', '').strip() or request.GET.get('token', '').strip()
        if query_key:
            return query_key
            
    return ''

def authenticate_request(request, required_type: str = 'write') -> tuple[bool, str]:
    allow_query = (required_type == 'read')
    token = extract_token_from_request(request, allow_query_param=allow_query)
    
    if not token:
        return False, 'API anahtarı bulunamadı. Lütfen Authorization başlığı (Bearer), X-API-Key veya URL parametresi (?key=) ile geçerli bir anahtar sağlayın.'
        
    env_key = getattr(settings, 'WRITE_API_KEY', '') if required_type == 'write' else getattr(settings, 'READ_API_KEY', '')
    if env_key and token == env_key.strip():
        return True, 'env'
        
    token_hash = hash_token(token)
    api_key_obj = ApiKey.objects.filter(key_hash=token_hash, key_type=required_type, is_active=True).first()
    if api_key_obj:
        api_key_obj.last_used_at = timezone.now()
        api_key_obj.save(update_fields=['last_used_at'])
        return True, f'db:{api_key_obj.id}'
        
    return False, 'Geçersiz veya yetkisiz API anahtarı.'
