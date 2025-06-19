import docker
import time
from dns_sync import process_container, remove_container
from database import init_db
import os

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
                    process_container(container)
                elif action == 'die':
                    remove_container(container_id)
            except Exception as e:
                print(f"Error processing container {container_id}: {e}")

def initial_sync():
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    containers = client.containers.list()
    for container in containers:
        try:
            process_container(container)
        except Exception as e:
            print(f"Initial sync error for {container.name}: {e}")

if __name__ == "__main__":
    init_db()
    initial_sync()
    while True:
        try:
            event_listener()
        except Exception as e:
            print(f"Listener error: {e}, restarting in {CHECK_INTERVAL}s.")
            time.sleep(CHECK_INTERVAL)
