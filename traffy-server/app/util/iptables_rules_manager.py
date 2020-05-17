import config
import os
import subprocess
import logging


def apply_redirect_rule(delete=False):
    ports = ["80"]
    chain_rule = "-A"

    if delete is True:
        chain_rule = "-D"

    for port in ports:
        for subnet in config.IP_RANGES:
            ip_range = subnet[2] + "-" + subnet[3]

            subprocess.Popen([
                "sudo",
                "iptables",
                "-t",
                "nat",
                chain_rule,
                "PREROUTING",
                "-m",
                "iprange",
                "--src-range",
                ip_range,
                "-p",
                "tcp",
                "--dport",
                port,
                "-j",
                "DNAT",
                "--to-destination",
                subnet[1]
                ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()
        
        for subnet in config.IP_RANGES:
            ip_range = subnet[2] + "-" + subnet[3]

            subprocess.Popen([
                "sudo",
                "iptables",
                "-t",
                "nat",
                chain_rule,
                "PREROUTING",
                "-m",
                "iprange",
                "--src-range",
                ip_range,
                "-p",
                "tcp",
                "--dport",
                "443",
                "-d",
                subnet[1],
                "-j",
                "ACCEPT"
                ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()
            
            subprocess.Popen([
                "sudo",
                "iptables",
                "-t",
                "nat",
                chain_rule,
                "PREROUTING",
                "-m",
                "iprange",
                "--src-range",
                ip_range,
                "-p",
                "tcp",
                "--dport",
                "443",
                "-d",
                config.WAN_IP_ADDRESS,
                "-j",
                "ACCEPT"
                ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.info("Applied captive portal ACLs")

def create_portal_box(delete=False):
    action = "-N"

    if delete is True:
        action = "-X"

    subprocess.Popen([
        "sudo",
        "iptables",
        action,
        "PORTAL"
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

def create_portal_route(delete=False):
    action = "-I"

    if delete is True:
        action = "-D"

    subprocess.Popen([
        "sudo",
        "iptables",
        action,
        "FORWARD",
        "-j",
        "PORTAL"
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

def attach_traffic_to_portal(delete=False):
    directions = ["INPUT", "OUTPUT"]
    action = "-I"

    if delete is True:
        action = "-D"

    for direction in directions:
        subprocess.Popen([
            "sudo",
            "iptables",
            action,
            direction,
            "-j",
            "PORTAL"
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

def apply_dns_rule(delete=False):
    protocols = ["tcp", "tcp", "udp", "udp"]
    port_argument = ["--dport", "--sport", "--dport", "--sport"]
    states = ["NEW,ESTABLISHED", "ESTABLISHED", "NEW,ESTABLISHED", "ESTABLISHED"]
    additional = ["--syn", "--syn"]
    chain = "-I"

    if delete is True:
        chain = "-D"

    for parameter in range(0, 4):
        for subnet in config.IP_RANGES:
            ip_range = subnet[2] + "-" + subnet[3]

            subprocess.Popen([
                "sudo",
                "iptables",
                "-t",
                "filter",
                chain,
                "PORTAL",
                "-m",
                "iprange",
                "--src-range",
                ip_range,
                "-p",
                protocols[parameter],
                port_argument[parameter],
                "53",
                "-m",
                "state",
                "--state",
                states[parameter],
                "-m",
                "limit",
                "--limit",
                "1/s",
                "--limit-burst",
                "30",
                "-j",
                "ACCEPT"
                ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.info("Applied DNS tunnel protection")

def apply_block_rule(delete=False):
    chain = "-I"

    if delete is True:
        chain = "-D"

    for subnet in config.IP_RANGES:
        ip_range = subnet[2] + "-" + subnet[3]

        subprocess.Popen([
            "sudo",
            "iptables",
            "-t",
            "filter",
            chain,
            "PORTAL",
            "-m",
            "iprange",
            "--src-range",
            ip_range,
            "-j",
            "DROP"
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()


    for subnet in config.IP_RANGES:
        ip_range = subnet[2] + "-" + subnet[3]

        excluded_ips = [subnet[1], config.WAN_IP_ADDRESS]

        for ip in excluded_ips:
            subprocess.Popen([
                "sudo",
                "iptables",
                "-t",
                "filter",
                chain,
                "PORTAL",
                "-m",
                "iprange",
                "--src-range",
                ip_range,
                "-d",
                ip,
                "-j",
                "ACCEPT"
                ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.info("Applied unregistered users ACL")

def unlock_registered_device(ip_address):
    table = ["nat", "filter"]
    chain = ["PREROUTING", "PORTAL"]

    for parameter in range(0, 2):
        subprocess.Popen([
            "sudo",
            "iptables",
            "-t",
            table[parameter],
            "-I",
            chain[parameter],
            "-s",
            ip_address,
            "-j",
            "RETURN"
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.debug("Added registration rule of " + ip_address)

def relock_registered_device(ip_address):
    table = ["nat", "filter"]
    chain = ["PREROUTING", "PORTAL"]

    for parameter in range(0, 2):
        subprocess.Popen([
            "sudo",
            "iptables",
            "-t",
            table[parameter],
            "-D",
            chain[parameter],
            "-s",
            ip_address,
            "-j",
            "RETURN"
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.debug("Cleared registration rule of " + ip_address)

