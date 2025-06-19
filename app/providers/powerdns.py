import os
import requests

class PowerDNSProvider:
    def __init__(self):
        self.api_url = os.getenv('PDNS_API_URL')
        self.api_key = os.getenv('PDNS_API_KEY')
        self.zone = os.getenv('PDNS_ZONE')

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
        requests.patch(url, json=data, headers=headers).raise_for_status()

    def delete_record(self, name, record_type="A"):
        headers = {"X-API-Key": self.api_key}
        data = {
            "rrsets": [{
                "name": f"{name}.",
                "type": record_type,
                "changetype": "DELETE"
            }]
        }
        url = f"{self.api_url}/servers/localhost/zones/{self.zone}"
        requests.patch(url, json=data, headers=headers).raise_for_status()
