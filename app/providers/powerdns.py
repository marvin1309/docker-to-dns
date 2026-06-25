import os
import logging
import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except ImportError:  # pragma: no cover
    Retry = None


class PowerDNSProvider:
    def __init__(self):
        self.api_url = os.getenv('PDNS_API_URL')
        self.api_key = os.getenv('PDNS_API_KEY')
        self.zone = os.getenv('PDNS_ZONE')
        self.timeout = float(os.getenv('PDNS_API_TIMEOUT', '10'))

        if not all([self.api_url, self.api_key, self.zone]):
            raise ValueError("❌ PDNS_API_URL, PDNS_API_KEY und PDNS_ZONE müssen gesetzt sein.")

        self.logger = logging.getLogger(self.__class__.__name__)

        # Reused session with bounded retries for transient errors (no infinite hangs).
        self.session = requests.Session()
        self.session.headers.update({"X-API-Key": self.api_key})
        if Retry is not None:
            retry = Retry(total=3, backoff_factor=0.5,
                          status_forcelist=(429, 500, 502, 503, 504),
                          allowed_methods=frozenset({"PATCH", "GET"}))
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

        self.logger.info(f"📡 PowerDNSProvider initialisiert mit Zone '{self.zone}'")

    @property
    def _zone_url(self):
        return f"{self.api_url}/servers/localhost/zones/{self.zone}"

    def _patch(self, data):
        """Single point for the PATCH call. Raises on HTTP/transport error."""
        response = self.session.patch(self._zone_url, json=data, timeout=self.timeout)
        response.raise_for_status()
        return response

    def create_record(self, name, content, record_type="A", ttl=300):
        """Create/replace an A record. RAISES on failure so callers don't record
        a success in the DB for a record PowerDNS actually rejected."""
        data = {
            "rrsets": [{
                "name": f"{name}.",
                "type": record_type,
                "ttl": ttl,
                "changetype": "REPLACE",
                "records": [{"content": content, "disabled": False}],
            }]
        }
        try:
            self._patch(data)
            self.logger.info(f"✅ DNS-Eintrag erstellt/aktualisiert: {name} → {content}")
        except requests.RequestException as e:
            self.logger.error(f"❌ Fehler beim Erstellen des DNS-Eintrags '{name}': {e}")
            raise

    def delete_record(self, name, record_type="A"):
        """Delete the record. Best-effort (logs, does not raise) — a missing record
        on delete is acceptable and must not block cleanup of other records."""
        data = {
            "rrsets": [{
                "name": f"{name}.",
                "type": record_type,
                "changetype": "DELETE",
            }]
        }
        try:
            self._patch(data)
            self.logger.info(f"🗑️ DNS-Eintrag gelöscht: {name}")
        except requests.RequestException as e:
            self.logger.warning(f"⚠️ Fehler beim Löschen des DNS-Eintrags '{name}': {e}")
