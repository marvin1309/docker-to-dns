import docker
import os
import logging
from providers import get_provider
from database import update_record, delete_record, get_record

# Logging-Setup
logger = logging.getLogger(__name__)

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
    host_ip = os.getenv("PDNS_HOST_IP")

    if not host_ip:
        logger.error("❌ Umgebungsvariable PDNS_HOST_IP fehlt – kann DNS nicht setzen.")
        return

    logger.info(f"Processing container {container.name} ({container.short_id}) with host IP {host_ip}")

    for label in labels:
        if label.startswith("auto-dns.customDNS."):
            service_name = label.split(".")[-1]
            try:
                dns_name = build_dns_name(labels, service_name)
                old_dns = get_record(container_id)
                if old_dns and old_dns != dns_name:
                    logger.info(f"Replacing old DNS record: {old_dns} → {dns_name}")
                    provider.delete_record(old_dns)

                provider.create_record(dns_name, host_ip)
                update_record(container_id, dns_name, host_ip)
                logger.info(f"✅ Created DNS record: {dns_name} → {host_ip}")

                # Optional: Wildcard
                wildcard = labels.get(f"auto-dns.createWildcard.{service_name}", "false").lower() == "true"
                if wildcard:
                    wildcard_name = f"*.{dns_name}"
                    provider.create_record(wildcard_name, host_ip)
                    logger.info(f"🌐 Created wildcard DNS: {wildcard_name} → {host_ip}")
            except ValueError as e:
                logger.warning(f"⚠️ Label issue in container '{container.name}': {e}")
            except Exception as e:
                logger.error(f"❌ Failed to process DNS for container '{container.name}': {e}")

def remove_container(container_id):
    dns_name = get_record(container_id)
    if dns_name:
        try:
            provider.delete_record(dns_name)
            delete_record(container_id)
            logger.info(f"🧹 Removed DNS record for container {container_id}: {dns_name}")
        except Exception as e:
            logger.error(f"❌ Failed to remove DNS record for container {container_id}: {e}")
