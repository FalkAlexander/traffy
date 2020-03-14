import config
import os
import subprocess
import logging


class DnsmasqService():
    dnsmasq = NotImplemented

    def start(self):
        logging.info("Starting DHCP server")
        executable = "dnsmasq"
        port = "--port=" + "0"
        interfaces = []
        for interface in config.IP_RANGES:
            interfaces.append("--interface=" + interface[0])
        conf = "--conf-file=" + config.DNSMASQ_CONFIG_FILE
        hosts = "--dhcp-hostsfile=" + config.DNSMASQ_HOSTS_FILE
        lease_file = "--dhcp-leasefile=" + config.DNSMASQ_LEASE_FILE
        dhcp_ranges = []
        for subnet in config.IP_RANGES:
            dhcp_ranges.append("--dhcp-range=" + subnet[0] + "," + subnet[2] + "," + subnet[3] + ",15m")
        dhcp_options = []
        for gateway in config.IP_RANGES:
            dhcp_options.append("--dhcp-option=" + gateway[0] + ",3," + gateway[1])
        dhcp_options.append("--dhcp-option=6," + config.DNS_SERVER)
        force_lease = "--no-ping"
        authoritative = "--dhcp-authoritative" # edgy
        self.dnsmasq = subprocess.Popen(["sudo",
                                        executable,
                                        port,
                                        conf,
                                        #force_lease,
                                        #authoritative,
                                        hosts,
                                        lease_file
                                        ] + dhcp_ranges + interfaces + dhcp_options, stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

        logging.info("Started DHCP server ")

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

