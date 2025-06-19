import os
import logging
from .powerdns import PowerDNSProvider

# Logger einrichten
logger = logging.getLogger(__name__)

def get_provider():
    provider_name = os.getenv('DNS_PROVIDER', 'powerdns').lower()
    logger.info(f"🔌 DNS-Provider ausgewählt: {provider_name}")

    if provider_name == 'powerdns':
        logger.info("✅ PowerDNS-Provider initialisiert.")
        return PowerDNSProvider()
    
    logger.error(f"❌ Nicht unterstützter DNS-Provider: {provider_name}")
    raise ValueError(f"Unsupported DNS provider: {provider_name}")
