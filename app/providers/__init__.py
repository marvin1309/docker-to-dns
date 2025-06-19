from .powerdns import PowerDNSProvider
import os

def get_provider():
    provider_name = os.getenv('DNS_PROVIDER', 'powerdns').lower()

    if provider_name == 'powerdns':
        return PowerDNSProvider()
    
    raise ValueError(f"Unsupported DNS provider: {provider_name}")
