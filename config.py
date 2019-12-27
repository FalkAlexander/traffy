class Config:
    SECRET_KEY = "BnUlPYIj2ZzeTL1wv4IxzCsRtqcPJLpxvOv"
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    @staticmethod
    def init_app(app):
        pass


class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = "mysql://traffy_user:traffy_user@192.168.100.150/traffy"

    @classmethod
    def init_app(cls, app):
        Config.init_app(app)


config = {
    'production': ProductionConfig,
    'default': ProductionConfig
}

LANGUAGES = ["en", "de"]
DNSMASQ_CONFIG_FILE = "/home/traffy/dnsmasq/dnsmasq.conf"
DNSMASQ_HOSTS_FILE = "/home/traffy/dnsmasq/dnsmasq-hosts.conf"
DNSMASQ_LEASE_FILE = "/home/traffy/dnsmasq/dnsmasq.leases"
DNSMASQ_LISTEN_INTERFACE = "enp7s0"
BRIDGE_INGRESS_INTERFACE = "ifb0"
DNS_SERVER = "1.1.1.1" # 141.46.140.31
DAILY_TOPUP_VOLUME = 5368709120 # 5 GiB / in bytes
MAX_SAVED_VOLUME = 37580963840 # 35 GiB / in bytes
SHAPING_SPEED = "64kbit"
SHAPING_EXCEPTIONS = ["192.168.100.150",        # Local
                    "192.168.100.201",          # Local
                    "141.46.140.31",            # DNS Görlitz
                    "141.46.14.31",             # DNS Zittau
                    "141.46.8.0/24",            # HSZG network (public)
                    "141.46.14.0/24",           # HSZG network (public)
                    "141.46.21.0/24",           # HSZG network (public)
                    "141.46.254.0/24",          # HSZG network (public)
                    "141.46.141.0/24",          # HSZG network (internal)
                    "134.109.133.26",           # OPAL
                    "141.0.22.231",             # SWDD web
                    "141.30.0.0/16",            # TUD (public)
                    "141.76.0.0/16",            # TUD (public)
                    "1.1.1.1"]
MAX_MAC_ADDRESSES_PER_REG_KEY = 5
IP_RANGE_START = "10.90.0.2"
IP_RANGE_END = "10.90.0.254"
THIS_SERVER_IP_LAN = "10.90.0.1"
THIS_SERVER_IP_WAN = "192.168.100.150"

ADMIN_NAME = "Falk Seidl"
ADMIN_MAIL = "admin.goerlitz@wh.studentenwerk-dresden.de"
ADMIN_ROOM = "2521"

COMMUNITY = "Görlitz"
SMTP_SERVER = "smtp.hszg.de"
SMTP_PORT = "25"
