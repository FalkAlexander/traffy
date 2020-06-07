![](https://i.imgur.com/IVYH25L.png)

# Traffy - Dormitory Network Management
Traffy is an all-in-one management suite for the regulation of dormitory networks with the focus on ease of usibility for its users. It is specialized in dealing with huge amounts of users/tenants. It was initially developed for the student dormitory in Görlitz.

## Feature Overview
* 👨‍👩‍👧‍👦️ Tenant database with master data management
* 💻️ Automated network connection registration with device to user assignment, no software installation or manual interface configuration required
* 🚦️ Traffic accounting, rules, exceptions and more
* 🖥️ Intuitive and responsive web interface for users
* 🚨️ Administration web interface with statistics, monitoring and user/connection settings
* 🔒️ Security measures to prevent connection tampering

## Architecture
![](https://i.imgur.com/J9IyXvY.png)

# Installation

## Anleitung
#### LAN Netzwerkinterface (Mieter-LAN)
Über dieses Netzwerkinterface geht der Traffic von und zu den Mietern. Es könnte sich z.B. um einen Link vom (Aggregation) Switch zur LAN NIC des Servers handeln.

Konfigurationsdatei:
```
/etc/network/interfaces.d/lan
```

LAN-Interface = NIC zum Mieter-LAN (LAN)

LAN-Interface-IP/Gateway = IP des Servers und Gateway gleichermaßen für die User im Mieter-LAN

```
allow-hotplug <LAN-Interface>
auto <LAN-Interface>
iface <LAN-Interface> inet static
	address <LAN-Interface-IP>
	netmask <Subnetz-Maske>
	gateway <LAN-Interface-IP/Gateway>
```

Netzwerkdienst neustarten:
```
service networking restart
```

#### Forwarding aktivieren
Konfigurationsdatei:
```
/etc/sysctl.conf
```

```
net.ipv4.ip_forward=1
```

#### NAT aktivieren
Damit das LAN Interface Zugriff auf das WAN hat, muss ein internes NAT konfiguriert werden:

```
apt install iptables-persistent
```

Konfigurationsdatei:
```
/etc/iptables/rules.v4
```

WAN-Interface = NIC ins Internet

```
*nat
-A POSTROUTING -o <WAN-Interface> -j MASQUERADE
COMMIT
```

```
iptables-restore < /etc/iptables/rules.v4
```

#### Pseudo NIC hinzufügen
Intermediate Functional Block Kernel Modul beim Systemstart deklarieren:
```
/etc/modules
```
Modulname in Konfigurationsdatei aufnehmen:
```
ifb
```

Kernel Modul bei Bedarf laden:
```
modprobe ifb
```

Ein pseudo Interface ist ausreichend, daher Parameter spezifizieren:
```
/etc/modprobe.d/ifb_options.conf
```

```
options ifb numifbs=1
```

Interface beim Systemstart automatisch aktivieren:
```
/etc/network/interfaces
```

```
up ifconfig ifb0 up
```

#### Traffy Abhängigkeiten installieren
* sudo
* dnsmasq
* net-tools
* ipset
* mariadb-server
* nginx
* gunicorn3
* python3-pip
* python3-dev
* python3-setuptools
* python3-wheel
* python3-cffi
* python3-dateutil
* python3-mysqldb
* python3-flask
* python3-flask-sqlalchemy
* python3-flask-babel
* python3-flask-login
* build-essential
* libcairo2
* libpango-1.0-0
* libpangocairo-1.0-0
* libgdk-pixbuf2.0-0
* libffi-dev
* shared-mime-info

```
pip3 install Flask-WeasyPrint
pip3 install user-agents
```

#### Services aktivieren
```
systemctl enable mariadb nginx
systemctl start mariadb nginx
```

#### MySQL einrichten
```
mysql_secure_installation
mysql -u root -p
```

```
CREATE SCHEMA traffy;
CREATE USER 'traffy_user' IDENTIFIED BY '<password>';
GRANT USAGE ON *.* TO 'traffy_user'@localhost IDENTIFIED BY '<password>';
GRANT ALL privileges ON traffy.* TO 'traffy_user'@localhost;
FLUSH PRIVILEGES;
quit;
```

#### Nutzer erstellen
```
adduser traffy
usermod -aG sudo traffy
```

Whitelist an Befehlen in ```/etc/sudoers```anlegen:

```
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/iptables *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/tc *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/arp -s *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/arp -d *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/ipset create *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/ipset add *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/ipset destroy *
```

#### NGINX konfigurieren
Serverblock Konfiguration anlegen für reverse proxying:

```
nano /etc/nginx/sites-available/traffy.conf
```

```
server {
	listen 80;
	server_name <WAN-Interface-IP>;
	
	access_log /var/log/nginx/traffy.access.log;
	error_log /var/log/nginx/traffy.error.log;

	location / {
		proxy_pass http://127.0.0.1:5000;
		proxy_set_header Host $host;
		proxy_redirect off;
		proxy_set_header X-Real-IP $remote_addr;
		proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;	
		proxy_set_header X-Forwarded-Proto $scheme;
	}
}
```

Serverblock Konfiguration anlegen für protocol layer redirect:

```
nano /etc/nginx/sites-available/traffy-redirect.conf
```

```
server {
	listen 80;
	server_name <LAN-Interface-IP>;
	
	access_log /var/log/nginx/traffy-redirect.access.log;
	error_log /var/log/nginx/traffy-redirect.error.log;

	return 302 http://<WAN-Interface-IP>;
}

```

Serverblocks aktivieren:

```
ln -s /etc/nginx/sites-available/traffy.conf /etc/nginx/sites-enabled/traffy.conf
ln -s /etc/nginx/sites-available/traffy-redirect.conf /etc/nginx/sites-enabled/traffy-redirect.conf
```

```
systemctl restart nginx
```


#### Traffy herunterladen
In die Shell des Users ```traffy``` wechseln oder als dieser anmelden.

Dann an einem geeigneten Ort, an welchem der Nutzer ```traffy``` Berechtigungen zum Lesen, Schreiben und Ausführen besitzt, das Repository klonen:

```
cd ~
git clone https://gitlab.com/fseidl/traffy.git traffy-app
```

#### Systemd Service erstellen
```
touch /etc/systemd/system/traffy.service
```

Mit einem favorisiertem Editor die Service Datei bearbeiten:

```
nano /etc/systemd/system/traffy.service
```

```
[Unit]
Description=Traffy Accounting
After=network.target mariadb.service nginx.service
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User=traffy
Group=traffy
WorkingDirectory=/home/traffy/traffy-app
ExecStart=/home/traffy/traffy-app/boot.sh

[Install]
WantedBy=multi-user.target
```

```
systemctl enable traffy
```

#### Traffy starten
```
systemctl start traffy
```

# Einrichtung
Nach dem Start von Traffy die Administrationsseite aufrufen:

```
http://<WAN-Interface-IP>/admin
```

Mit den default Anmeldedaten einloggen:

User: ```admin```

Password: ```admin```

Anmeldedaten für den Produktivbetrieb unbedingt ändern!  
  
  
![](https://i.imgur.com/bLfPmcf.png)
