import os
import sys
import signal
import threading
import logging

import docker

from dns_sync import process_container, remove_container, reconcile
from database import init_db

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

DOCKER_HOST = os.getenv('DOCKER_HOST', 'unix://var/run/docker.sock')
CHECK_INTERVAL = int(os.getenv('CHECK_INTERVAL', '60'))          # listener reconnect backoff
RECONCILE_INTERVAL = int(os.getenv('RECONCILE_INTERVAL', '300'))  # periodic self-heal

# events that mean "(re)publish this container's DNS" vs "remove it"
START_ACTIONS = frozenset({'start', 'restart', 'update', 'unpause'})
STOP_ACTIONS = frozenset({'die'})

_stop = threading.Event()


def get_client():
    return docker.DockerClient(base_url=DOCKER_HOST)


def full_sync(client):
    """Reconcile DNS against all running containers (self-heals missed events)."""
    containers = client.containers.list()
    logger.info(f"Running reconcile for {len(containers)} containers")
    reconcile(containers)


def event_listener(client):
    """Block on the docker event stream and react to container lifecycle events."""
    for event in client.events(decode=True):
        if _stop.is_set():
            break
        if event.get('Type') != 'container':
            continue
        action = event.get('Action')
        container_id = event.get('id')
        try:
            if action in START_ACTIONS:
                container = client.containers.get(container_id)
                logger.info(f"Detected container '{container.name}' action: {action}")
                process_container(container)
            elif action in STOP_ACTIONS:
                logger.info(f"Detected container '{container_id}' stopped, cleaning up DNS")
                remove_container(container_id)
        except docker.errors.NotFound:
            # container vanished between event and lookup — let reconcile handle it
            logger.debug(f"Container {container_id} not found for action {action}")
        except Exception as e:  # noqa: BLE001
            logger.error(f"Error processing container {container_id}: {e}")


def reconcile_loop():
    """Background thread: periodic full reconcile to repair any drift."""
    while not _stop.wait(RECONCILE_INTERVAL):
        client = None
        try:
            client = get_client()
            full_sync(client)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Reconcile loop error: {e}")
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:  # noqa: BLE001
                    pass


def _handle_signal(signum, _frame):
    logger.info(f"Signal {signum} empfangen – fahre sauber herunter.")
    _stop.set()


def main():
    logger.info(f"🔥 Docker-to-DNS {os.getenv('APP_VERSION', 'dev')} gestartet")

    if not os.getenv("PDNS_HOST_IP"):
        logger.critical("❌ PDNS_HOST_IP ist nicht gesetzt! Container wird beendet.")
        sys.exit(1)

    init_db()  # raises and aborts startup if the DB is unusable

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    threading.Thread(target=reconcile_loop, name="reconcile", daemon=True).start()

    # Listener loop: reconnect on failure and ALWAYS re-sync first so events
    # missed during the outage are caught up.
    while not _stop.is_set():
        client = None
        try:
            client = get_client()
            full_sync(client)
            event_listener(client)
        except Exception as e:  # noqa: BLE001
            logger.error(f"Listener error: {e}, restarting in {CHECK_INTERVAL}s.")
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:  # noqa: BLE001
                    pass
        if not _stop.is_set():
            _stop.wait(CHECK_INTERVAL)

    logger.info("👋 Docker-to-DNS beendet.")


if __name__ == "__main__":
    main()
