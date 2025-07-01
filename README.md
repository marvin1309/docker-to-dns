
# 🐳 docker-to-dns

**docker-to-dns** ist ein leichtgewichtiger Docker-Dienst, der automatisch DNS-Einträge für deine Docker-Container erzeugt und verwaltet – insbesondere mit PowerDNS. Er synchronisiert Container-Events wie Start, Stopp oder Updates direkt mit dem DNS-Backend und sorgt so für stets aktuelle DNS-Zonen.

---

## 🔧 Features

- ✅ Automatische Erstellung & Löschung von DNS-A/AAAA-Einträgen
- 🔄 Realtime-Sync mit Docker Events (`start`, `restart`, `update`, `die`)
- 🗃️ SQLite-Datenbank zur Speicherung des Container-Zustands
- 🧠 Konfigurierbares DNS-Namensschema via Labels
- 🌐 Wildcard-Unterstützung pro Container
- 🌱 Minimaler Ressourcenverbrauch
- 📦 Bereitgestellt als Container über `ghcr.io`

---

## 🚀 Deployment

```bash
docker run -d \
  --name docker-to-dns \
  -v /var/run/docker.sock:/var/run/docker.sock \
  -e PDNS_API_KEY=your-secret-key \
  -e PDNS_API_URL=http://your-pdns-server:8081/api/v1 \
  -e PDNS_ZONE=example.com \
  -e PDNS_HOST_IP=10.1.1.100 \
  ghcr.io/marvin1309/docker-to-dns:latest
````

### ✏️ Environment-Variablen

| Variable | Beschreibung | Erforderlich |
| --- | --- | --- |
| `PDNS_API_KEY` | API Key für PowerDNS | ✅ |
| `PDNS_API_URL` | API URL des PowerDNS-Servers (`/api/v1`) | ✅ |
| `PDNS_ZONE` | DNS-Zone, z. B. `int.fam-feser.de` | ✅ |
| `PDNS_HOST_IP` | IP-Adresse des Hosts, die für Container als A-Record gesetzt wird | ✅ |
| `CHECK_INTERVAL` | Intervall für Reconnect bei Fehlern (Sekunden, default: `60`) | ❌ |
| `LOG_LEVEL` | Logging-Stufe (`DEBUG`, `INFO`, `WARNING`, ...) | ❌ |

* * *

🏷️ Label-Konventionen (`auto-dns.*`)
-------------------------------------

Um die DNS-Einträge pro Container zu definieren, nutze folgende Labels im Compose-File oder Docker-Run-Befehl:

| Label Key | Beschreibung | Beispiel |
| --- | --- | --- |
| `auto-dns.customDNS.<name>` | Ob der Container DNS erhalten soll (`true`/`false`) | `true` |
| `auto-dns.createWildcard.<name>` | Erstelle zusätzlich `*.name.domain`\-Eintrag | `true` |
| `auto-dns.domain.<name>` | Ziel-Domain (z. B. `int.fam-feser.de`) | `int.fam-feser.de` |
| `auto-dns.stage.<name>` | Optionaler Stage-Prefix (z. B. `prod`, `dev`) | `prod` |
| `auto-dns.service.<name>` | Servicename | `traefik` |
| `auto-dns.hostname.<name>` | Hostname/Instanzname (z. B. `hydra`) | `hydra` |

> 🔍 **FQDN-Logik**:  
> Falls `stage`, `hostname` oder `service` fehlen, wird automatisch reduziert:  
> `stage.service.hostname.domain` → `service.hostname.domain` → `service.domain`

* * *

📦 Beispiel (`docker-compose.yml`)
----------------------------------

``.yml
services:
  traefik:
    image: traefik:latest
    labels:
      - "auto-dns.customDNS.traefik=true"
      - "auto-dns.createWildcard.traefik=true"
      - "auto-dns.domain.traefik=int.fam-feser.de"
      - "auto-dns.stage.traefik=prod"
      - "auto-dns.service.traefik=traefik"
      - "auto-dns.hostname.traefik=hydra"
```

* * *

🧪 Logging
----------

Alle Container-Aktionen werden mit logischen Ausgaben versehen, z. B.:

```
2025-06-19 20:15:01 [INFO] 📡 PowerDNSProvider initialisiert mit Zone 'int.fam-feser.de'
2025-06-19 20:15:02 [INFO] ✅ DNS-Eintrag erstellt/aktualisiert: prod.traefik.hydra → 10.1.130.70
2025-06-19 20:18:14 [INFO] 🗑️ DNS-Eintrag gelöscht: prod.traefik.hydra
```

Setze `LOG_LEVEL=DEBUG`, um Details zu sehen.

* * *

🔭 Roadmap (geplant)
--------------------

*    Automodus (ohne Labels) mit heuristischer Namensbildung
    
*    Unterstützung für weitere DNS-Backends (z. B. CoreDNS, Cloudflare)
    
*    Web-UI zur DNS-Übersicht und manuellem Triggern
    
*    CI/CD Integration & Image-Scans
    

* * *

🛡️ Sicherheit
--------------

Stelle sicher, dass dein PowerDNS-API-Key **nur Rechte auf die nötigen Zonen** hat. Der Container benötigt **nur lesenden Zugriff auf den Docker-Socket** (`/var/run/docker.sock`), kein Root.

* * *

🧑‍💻 Mitwirken
---------------

Issues und Pull Requests willkommen! Dieses Projekt ist aktuell in aktiver Entwicklung und wird auf produktiven Hosts eingesetzt – mit Fokus auf Stabilität und Modularität.

* * *
