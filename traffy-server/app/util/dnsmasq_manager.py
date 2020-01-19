import config
import os
import subprocess
import logging


class DnsmasqService():
    dnsmasq = NotImplemented

    def start(self):
        logging.info("Starting DHCP server on interface " + config.DNSMASQ_LISTEN_INTERFACE)
        executable = "dnsmasq"
        port = "--port=" + "0"
        interface = "--interface=" + config.DNSMASQ_LISTEN_INTERFACE
        conf = "--conf-file=" + config.DNSMASQ_CONFIG_FILE
        hosts = "--dhcp-hostsfile=" + config.DNSMASQ_HOSTS_FILE
        lease_file = "--dhcp-leasefile=" + config.DNSMASQ_LEASE_FILE
        dhcp_range = "--dhcp-range=" + config.IP_RANGE_START + "," + config.IP_RANGE_END + ",15m"
        dhcp_option = "--dhcp-option=option:dns-server," + config.DNS_SERVER
        force_lease = "--no-ping"
        authoritative = "--dhcp-authoritative" # edgy
        self.dnsmasq = subprocess.Popen(["sudo",
                                        executable,
                                        port,
                                        interface,
                                        conf,
                                        #force_lease,
                                        authoritative,
                                        hosts,
                                        lease_file,
                                        dhcp_range,
                                        dhcp_option
                                         ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

        logging.info("Listening to " + config.IP_RANGE_START + " to " + config.IP_RANGE_END)

    def reload(self):
        if self.dnsmasq is NotImplemented:
            return

        subprocess.Popen(["sudo", "killall", "-u", "nobody", "-s", "HUP", "dnsmasq"], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()
        logging.info("Reloaded static DHCP leases")

    def stop(self):
        if self.dnsmasq is NotImplemented:
            return

        subprocess.Popen(["sudo", "killall", "-u", "nobody", "-s", "QUIT", "dnsmasq"], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()
        logging.info("Stopped DHCP server")

def add_static_lease(mac_address, ip_address):
    with open(config.DNSMASQ_HOSTS_FILE, "a") as host_file:
        host_file.write(mac_address + "," + ip_address + "\n")
    logging.debug("Added static lease: " + mac_address + " <-> " + ip_address)

def remove_static_lease(mac_address, ip_address):
    with open(config.DNSMASQ_HOSTS_FILE, "r") as host_file:
        cache = host_file.readlines()

    with open(config.DNSMASQ_HOSTS_FILE, "w") as host_file:
        for host in cache:
            if host != mac_address + "," + ip_address + "\n":
                host_file.write(host)

    logging.debug("Removed static lease: " + mac_address + " <-> " + ip_address)

def get_static_lease_mac(ip_address):
    mac_address = None
    with open(config.DNSMASQ_HOSTS_FILE, "r") as host_file:
        for line in host_file:
            pairs = line.split()
            for pair in pairs:
                elements = pair.split(",")
                if elements[1] == ip_address:
                    mac_address = elements[0]
                    break
    return mac_address

