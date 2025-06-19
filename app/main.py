import docker
import time
from dns_sync import process_container, remove_container
from database import init_db
import os
import logging

# Logging-Konfiguration
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()]
)

logger = logging.getLogger(__name__)

CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))

def event_listener():
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    for event in client.events(decode=True):
        if event['Type'] == 'container':
            action = event['Action']
            container_id = event['id']
            try:
                if action in ['start', 'restart', 'update']:
                    container = client.containers.get(container_id)
                    logger.info(f"Detected container '{container.name}' action: {action}")
                    process_container(container)
                elif action == 'die':
                    logger.info(f"Detected container '{container_id}' stopped, cleaning up DNS")
                    remove_container(container_id)
            except Exception as e:
                logger.error(f"Error processing container {container_id}: {e}")

def initial_sync():
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    containers = client.containers.list()
    logger.info(f"Running initial DNS sync for {len(containers)} containers")
    for container in containers:
        try:
            logger.info(f"Processing container: {container.name}")
            process_container(container)
        except Exception as e:
            logger.error(f"Initial sync error for {container.name}: {e}")

if __name__ == "__main__":
    logger.info("🔥 Docker-to-DNS gestartet")

    host_ip = os.getenv("PDNS_HOST_IP")
    if not host_ip:
        logger.critical("❌ PDNS_HOST_IP ist nicht gesetzt! Container wird beendet.")
        exit(1)

    init_db()
    initial_sync()
    while True:
        try:
            event_listener()
        except Exception as e:
            logger.error(f"Listener error: {e}, restarting in {CHECK_INTERVAL}s.")
            time.sleep(CHECK_INTERVAL)
