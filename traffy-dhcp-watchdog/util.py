from scapy.all import *
import config
import os
import random
import subprocess


def get_leases():
    leases = []
    with open(config.DNSMASQ_LEASE_FILE, "r") as lease_file:
        for line in lease_file:
            lease = line.split()
            leases.append([lease[1], lease[2]])
    
    return leases

def release(ip_address, mac_address):
    release_mac=mac2str(mac_address)
    server_ip=config.DHCP_INTERFACE_IP
    send(IP(src=ip_address, dst=server_ip) / 
        UDP(sport=68,dport=67) /
        BOOTP(chaddr=release_mac, ciaddr=ip_address, xid=random.randint(0, 0xFFFFFFFF)) /
        DHCP(options=[("message-type", "release"), ("server_id", server_ip), "end"]))

def arping(ip_address):
    proc = subprocess.Popen([
            "sudo",
            "arping",
            ip_address,
            "-c",
            str(config.PING_TRIES)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    proc.wait()
    stdout = proc.communicate()[0].decode("utf-8")

    if "100% unanswered" in stdout:
        return False
    else:
        return True
