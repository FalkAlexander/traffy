DATABASE_URI = "mysql://traffy_user:traffy_user@192.168.100.150/traffy_server"
DNSMASQ_CONFIG_FILE = "/home/traffy/dnsmasq/dnsmasq.conf"
DNSMASQ_HOSTS_FILE = "/home/traffy/dnsmasq/dnsmasq-hosts.conf"
DNSMASQ_LEASE_FILE = "/home/traffy/dnsmasq/dnsmasq.leases"
DNSMASQ_LISTEN_INTERFACE = "enp7s0"
BRIDGE_INGRESS_INTERFACE = "ifb0"
DNS_SERVER = "141.46.14.31" # 141.46.140.31
DAILY_TOPUP_VOLUME = 5368709120 # 5 GiB / in bytes
MAX_SAVED_VOLUME = 37580963840 # 35 GiB / in bytes
MAX_MAC_ADDRESSES_PER_REG_KEY = 5
IP_RANGE_START = "10.90.0.2"
IP_RANGE_END = "10.90.0.254"
THIS_SERVER_IP_LAN = "10.90.0.1"
THIS_SERVER_IP_WAN = "192.168.100.150"
SMTP_SERVER = "smtp.hszg.de"
SMTP_PORT = "25"
SHAPING_SPEED = "64kbit"
SHAPING_EXCEPTIONS = [THIS_SERVER_IP_WAN,       # Local
                    THIS_SERVER_IP_LAN,         # Local
                    "192.168.100.201",          # Test
                    "141.46.0.0/16",            # HSZG
                    "134.109.0.0/16",           # TU Chemnitz / OPAL
                    "141.0.22.231",             # SWDD web
                    "141.30.0.0/16",            # TUD (public)
                    "141.76.0.0/16",            # TUD (public)
                    "193.174.102.0/23",         # GR-NET
                    "193.174.8.0/24",           # GR-NET
                    "195.37.50.0/24",           # GR-NET
                    "195.37.162.0/24",          # GR-NET
                    "141.56.0.0/16",            # HTW
                    "141.43.0.0/16"]            # B-TU

