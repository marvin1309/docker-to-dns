import os
import logging

from providers import get_provider
from database import (
    update_record, delete_record, get_records, get_all_records,
    dns_name_claimed_by_other,
)

logger = logging.getLogger(__name__)

# Lazy, cached provider so importing this module has no side effects (testable)
# and a missing env var fails where it is used, not at import time.
_provider = None


def get_active_provider():
    global _provider
    if _provider is None:
        _provider = get_provider()
    return _provider


def _host_ip():
    return os.getenv("PDNS_HOST_IP")


def build_dns_name(labels, service_name):
    custom_dns = labels.get(f"auto-dns.customDNS.{service_name}", "false").lower() == "true"

    if custom_dns:
        domain = labels.get(f"auto-dns.customDOMAIN.{service_name}")
        host = labels.get(f"auto-dns.customHost.{service_name}")
        if not all([domain, host]):
            raise ValueError(f"Missing labels for custom DNS: {service_name}")
        return f"{host}.{domain}"

    domain = labels.get(f"auto-dns.domain.{service_name}")
    stage = labels.get(f"auto-dns.stage.{service_name}")
    service = labels.get(f"auto-dns.service.{service_name}")
    hostname = labels.get(f"auto-dns.hostname.{service_name}")
    if not all([domain, stage, service, hostname]):
        raise ValueError(f"Missing labels for auto DNS: {service_name}")
    return f"{stage}.{service}.{hostname}.{domain}"


def desired_records(container):
    """Compute the desired DNS records for a container from its labels.

    A container may declare MANY `auto-dns.customDNS.<service>` labels; each maps
    to its own record. Returns a list of (dns_name, wildcard_bool); invalid label
    sets are skipped with a warning so one bad service can't abort processing.
    """
    out = []
    seen = set()
    labels = container.labels or {}
    for label in labels:
        if not label.startswith("auto-dns.customDNS."):
            continue
        service_name = label.split(".")[-1]
        try:
            dns_name = build_dns_name(labels, service_name)
        except ValueError as e:
            logger.warning(f"⚠️ Label issue in container '{container.name}': {e}")
            continue
        if dns_name in seen:
            continue
        seen.add(dns_name)
        wildcard = labels.get(
            f"auto-dns.createWildcard.{service_name}", "false").lower() == "true"
        out.append((dns_name, wildcard))
    return out


def _apply_record(provider, dns_name, host_ip, wildcard):
    """Create the A record (and wildcard) in DNS. Raises if the primary record
    fails so the caller skips the DB write."""
    provider.create_record(dns_name, host_ip)
    if wildcard:
        provider.create_record(f"*.{dns_name}", host_ip)


def _remove_dns(provider, dns_name):
    """Best-effort delete of the record and its wildcard."""
    provider.delete_record(dns_name)
    provider.delete_record(f"*.{dns_name}")


def process_container(container):
    host_ip = _host_ip()
    if not host_ip:
        logger.error("❌ Umgebungsvariable PDNS_HOST_IP fehlt – kann DNS nicht setzen.")
        return

    provider = get_active_provider()
    container_id = container.id
    logger.info(f"Processing container {container.name} ({container.short_id}) with host IP {host_ip}")

    desired = desired_records(container)
    desired_names = {name for name, _ in desired}

    # drop records this container previously owned but no longer declares
    for old_name in get_records(container_id):
        if old_name not in desired_names and not dns_name_claimed_by_other(container_id, old_name):
            logger.info(f"Removing stale DNS record for {container.name}: {old_name}")
            try:
                _remove_dns(provider, old_name)
                delete_record(container_id, old_name)
            except Exception as e:  # noqa: BLE001
                logger.error(f"❌ Failed to drop stale record {old_name}: {e}")

    for dns_name, wildcard in desired:
        try:
            _apply_record(provider, dns_name, host_ip, wildcard)
            # only persist AFTER DNS actually accepted the record
            update_record(container_id, dns_name, host_ip)
            logger.info(f"✅ Created DNS record: {dns_name} → {host_ip}")
            if wildcard:
                logger.info(f"🌐 Created wildcard DNS: *.{dns_name} → {host_ip}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"❌ Failed to process DNS for container '{container.name}': {e}")


def remove_container(container_id):
    names = get_records(container_id)
    if not names:
        return
    provider = get_active_provider()
    try:
        for dns_name in names:
            # Guard: do not delete a record a different (e.g. freshly-recreated)
            # container now owns.
            if dns_name_claimed_by_other(container_id, dns_name):
                logger.info(f"↪️ Keeping DNS '{dns_name}' (claimed by another container)")
            else:
                _remove_dns(provider, dns_name)
                logger.info(f"🧹 Removed DNS record for container {container_id}: {dns_name}")
        delete_record(container_id)  # drop all rows for this (gone) container
    except Exception as e:  # noqa: BLE001
        logger.error(f"❌ Failed to remove DNS records for container {container_id}: {e}")


def reconcile(containers):
    """Self-healing full sync: make DNS + DB match the set of running containers.

    Catches anything missed while the event listener was down and removes orphaned
    records left by missed `die` events (the drift seen "after a long time" /
    "after backups"). Multi-record aware.
    """
    host_ip = _host_ip()
    if not host_ip:
        logger.error("❌ PDNS_HOST_IP fehlt – Reconcile übersprungen.")
        return

    provider = get_active_provider()
    desired_pairs = set()   # (container_id, dns_name)
    desired_names = set()   # dns_name (any container)
    wildcards = {}          # (container_id, dns_name) -> wildcard
    for c in containers:
        for dns_name, wildcard in desired_records(c):
            desired_pairs.add((c.id, dns_name))
            desired_names.add(dns_name)
            wildcards[(c.id, dns_name)] = wildcard

    db_pairs = {(cid, name) for cid, name, _ip in get_all_records()}

    # 1) remove orphans: DB rows not desired anymore. Only touch DNS if NO running
    #    container still wants that name (another may legitimately own it).
    for container_id, dns_name in db_pairs - desired_pairs:
        logger.info(f"🧽 Reconcile: removing orphan {container_id} → {dns_name}")
        try:
            if dns_name not in desired_names:
                _remove_dns(provider, dns_name)
            delete_record(container_id, dns_name)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"⚠️ Reconcile cleanup failed for {dns_name}: {e}")

    # 2) ensure every desired record exists (idempotent REPLACE in PowerDNS)
    for container_id, dns_name in desired_pairs - db_pairs:
        try:
            _apply_record(provider, dns_name, host_ip, wildcards[(container_id, dns_name)])
            update_record(container_id, dns_name, host_ip)
            logger.info(f"🔁 Reconcile: ensured {dns_name} → {host_ip}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"❌ Reconcile failed for {dns_name}: {e}")
