import docker
from providers import get_provider
from database import update_record, delete_record, get_record
import os

provider = get_provider()
client = docker.DockerClient(base_url='unix://var/run/docker.sock')

def build_dns_name(labels, service_name):
    custom_dns = labels.get(f"auto-dns.customDNS.{service_name}", "false").lower() == "true"
    
    if custom_dns:
        domain = labels.get(f"auto-dns.customDOMAIN.{service_name}")
        host = labels.get(f"auto-dns.customHost.{service_name}")
        if not all([domain, host]):
            raise ValueError(f"Missing labels for custom DNS: {service_name}")
        return f"{host}.{domain}"
    else:
        domain = labels.get(f"auto-dns.domain.{service_name}")
        stage = labels.get(f"auto-dns.stage.{service_name}")
        service = labels.get(f"auto-dns.service.{service_name}")
        hostname = labels.get(f"auto-dns.hostname.{service_name}")
        if not all([domain, stage, service, hostname]):
            raise ValueError(f"Missing labels for auto DNS: {service_name}")
        return f"{stage}.{service}.{hostname}.{domain}"

def process_container(container):
    labels = container.labels
    container_id = container.id
    ip = container.attrs['NetworkSettings']['IPAddress']

    for label in labels:
        if label.startswith("auto-dns.customDNS."):
            service_name = label.split(".")[-1]
            try:
                dns_name = build_dns_name(labels, service_name)
                old_dns = get_record(container_id)
                if old_dns and old_dns != dns_name:
                    provider.delete_record(old_dns)
                provider.create_record(dns_name, ip)
                update_record(container_id, dns_name, ip)

                # Wildcard handling
                wildcard = labels.get(f"auto-dns.createWildcard.{service_name}", "false").lower() == "true"
                if wildcard:
                    wildcard_name = f"*.{dns_name}"
                    provider.create_record(wildcard_name, ip)
            except ValueError as e:
                print(f"Label issue in container {container.name}: {e}")

def remove_container(container_id):
    dns_name = get_record(container_id)
    if dns_name:
        provider.delete_record(dns_name)
        delete_record(container_id)
