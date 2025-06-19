class PowerDNSProvider:
    def __init__(self):
        self.api_url = os.getenv('PDNS_API_URL')
        self.api_key = os.getenv('PDNS_API_KEY')
        self.zone = os.getenv('PDNS_ZONE')

        if not all([self.api_url, self.api_key, self.zone]):
            raise ValueError("❌ PDNS_API_URL, PDNS_API_KEY und PDNS_ZONE müssen gesetzt sein.")
        
        self.logger = logging.getLogger(self.__class__.__name__)
        self.logger.info(f"📡 PowerDNSProvider initialisiert mit Zone '{self.zone}'")

    def create_record(self, name, content, record_type="A", ttl=300):
        headers = {"X-API-Key": self.api_key}
        data = {
            "rrsets": [{
                "name": f"{name}.",
                "type": record_type,
                "ttl": ttl,
                "changetype": "REPLACE",
                "records": [{"content": content, "disabled": False}]
            }]
        }
        url = f"{self.api_url}/servers/localhost/zones/{self.zone}"
        try:
            response = requests.patch(url, json=data, headers=headers)
            response.raise_for_status()
            self.logger.info(f"✅ DNS-Eintrag erstellt/aktualisiert: {name} → {content}")
        except requests.RequestException as e:
            self.logger.error(f"❌ Fehler beim Erstellen des DNS-Eintrags '{name}': {e}")

    def delete_record(self, name, record_type="A"):
        headers = {"X-API-Key": self.api_key}
        url = f"{self.api_url}/servers/localhost/zones/{self.zone}"

        def send_delete(target_name):
            data = {
                "rrsets": [{
                    "name": f"{target_name}.",
                    "type": record_type,
                    "changetype": "DELETE"
                }]
            }
            try:
                response = requests.patch(url, json=data, headers=headers)
                response.raise_for_status()
                self.logger.info(f"🗑️ DNS-Eintrag gelöscht: {target_name}")
            except requests.RequestException as e:
                self.logger.warning(f"⚠️ Fehler beim Löschen des DNS-Eintrags '{target_name}': {e}")

        # Normaler Eintrag
        send_delete(name)

        # Wildcard-Eintrag zusätzlich löschen
        wildcard_name = f"*.{name}"
        send_delete(wildcard_name)
