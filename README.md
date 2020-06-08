![](https://i.imgur.com/IVYH25L.png)

# Traffy - Dormitory Network Management
Traffy is an all-in-one management suite for the regulation of dormitory networks with the focus on ease of usability for its users. It is specialized in dealing with huge amounts of users/tenants. It got initially developed for the student dormitory in Görlitz.

## Feature Overview
* 👨‍👩‍👧‍👦️ Tenant database with master data management
* 💻️ Automated network connection registration with device to user assignment, no software installation or manual interface configuration required
* 🚦️ Traffic accounting, rules, exceptions and more
* 🖥️ Intuitive and responsive web interface for users
* 🚨️ Administration web interface with statistics, monitoring and user/connection settings
* 🔒️ Security measures to prevent connection tampering

## Architecture
![](https://i.imgur.com/J9IyXvY.png)

## Example Installation Instruction (only suited for development environments)
#### LAN Network Interface (Tenant-LAN)
This is the interface which is responsible for connecting the tenants with the router (line between router/server and tenant device).

Configuration:
```
/etc/network/interfaces.d/lan
```

LAN-Interface = NIC to the Tenant-LAN (LAN)

LAN-Interface-IP/Gateway = IP of the server/gateway for the users in the LAN

```
allow-hotplug <LAN-Interface>
auto <LAN-Interface>
iface <LAN-Interface> inet static
	address <LAN-Interface-IP>
	netmask <Subnet-Mask>
	gateway <LAN-Interface-IP/Gateway>
```

Restart networking service:
```
service networking restart
```

#### Enable forwarding
```
/etc/sysctl.conf
```

```
net.ipv4.ip_forward=1
```

#### Activate internal NAT (alternative: use routes)
Configure an internal NAT in order to interconnect the networks of the WAN and LAN NICs:

```
apt install iptables-persistent
```

```
/etc/iptables/rules.v4
```

WAN-Interface = NIC to the Internet

```
*nat
-A POSTROUTING -o <WAN-Interface> -j MASQUERADE
COMMIT
```

```
iptables-restore < /etc/iptables/rules.v4
```

#### Add pseudo NIC
The pseudo NIC is required in order to allow the shaping of outgoing traffic.
Declare Intermediate Functional Block Kernel Module:
```
/etc/modules
```
Add module to configuration:
```
ifb
```

Load kernel module at runtime:
```
modprobe ifb
```

Count of pseudo NICs, in this case one is sufficient:
```
/etc/modprobe.d/ifb_options.conf
```

```
options ifb numifbs=1
```

Enable pseudo NIC on boot:
```
/etc/network/interfaces
```

```
up ifconfig ifb0 up
```

#### Traffy dependencies
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
* python3-git
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

#### Enable services
```
systemctl enable mariadb nginx
systemctl start mariadb nginx
```

#### MySQL
```
mysql_secure_installation
mysql -u root -p
```

```
CREATE SCHEMA traffy_server;
CREATE SCHEMA traffy_web;
CREATE USER 'traffy_user' IDENTIFIED BY '<password>';
GRANT USAGE ON *.* TO 'traffy_user'@localhost IDENTIFIED BY '<password>';
GRANT ALL privileges ON traffy_server.* TO 'traffy_user'@localhost;
GRANT ALL privileges ON traffy_web.* TO 'traffy_user'@localhost;
FLUSH PRIVILEGES;
quit;
```

#### Create user
```
adduser traffy
usermod -aG sudo traffy
```

Add sudo command whitelist ```/etc/sudoers```:

```
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/iptables *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/tc *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/arp -s *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/arp -d *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/ipset create *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/ipset add *
traffy  ALL=(ALL:ALL) NOPASSWD:/usr/sbin/ipset destroy *
```

#### Configure NGINX reverse proxying
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

Serverblock configuration for protocol layer redirect:

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

Enable serverblocks:

```
ln -s /etc/nginx/sites-available/traffy.conf /etc/nginx/sites-enabled/traffy.conf
ln -s /etc/nginx/sites-available/traffy-redirect.conf /etc/nginx/sites-enabled/traffy-redirect.conf
```

```
systemctl restart nginx
```


#### Download Traffy
```
cd ~
git clone https://gitlab.com/fseidl/traffy.git traffy-app
```

#### Create systemd services
```
touch /etc/systemd/system/traffy.service
```

Mit einem favorisiertem Editor die Service Datei bearbeiten:

```
nano /etc/systemd/system/traffy-server.service
```

```
[Unit]
Description=Traffy Server
After=network.target mariadb.service nginx.service dnsmasq.service
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User=traffy
Group=traffy
WorkingDirectory=<path-to-traffy-server-directory>
ExecStart=python3 server.py
KillMode=mixed

[Manager]
TimeoutStopSec=300s
DefaultRestartSec=300s

[Install]
WantedBy=multi-user.target
```

```
nano /etc/systemd/system/traffy-web.service
```

```
[Unit]
Description=Traffy Web Client Stable
After=network.target nginx.service traffy-stable-server.service
StartLimitIntervalSec=0

[Service]
Type=simple
Restart=always
RestartSec=1
User=traffy
Group=traffy
WorkingDirectory=<path-to-traffy-web-directory>
ExecStart=gunicorn3 -b :5000 -c hooks.py web:app
KillMode=mixed

[Install]
WantedBy=multi-user.target
```

```
systemctl enable traffy-server traffy-web
```

#### Start Traffy
```
systemctl start traffy-server traffy-web
```

# Administration Interface
Go to:

```
http://<WAN-Interface-IP>/admin
```

Default credentials:

User: ```admin```

Password: ```admin```
  
  
![](https://i.imgur.com/bLfPmcf.png)
