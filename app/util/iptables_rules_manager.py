import config
import os
import subprocess
import logging


def apply_redirect_rule(delete=False):
    ports = ["80", "443"]
    ip_range = config.IP_RANGE_START + "-" + config.IP_RANGE_END
    chain_rule = "-A"

    if delete is True:
        chain_rule = "-D"

    for port in ports:
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
            config.THIS_SERVER_IP + ":80"
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

#    subprocess.Popen([
#            "sudo",
#            "iptables",
#            "-t",
#            "nat",
#            "-A",
#            "POSTROUTING",
#            "-j",
#            "MASQUERADE"
#            ], stdout=subprocess.PIPE, preexec_fn=os.setsid)

    logging.info("Applied captive portal ACLs")

def apply_dns_rule(delete=False):
    ip_range = config.IP_RANGE_START + "-" + config.IP_RANGE_END
    protocols = ["tcp", "tcp", "udp", "udp"]
    port_argument = ["--dport", "--sport", "--dport", "--sport"]
    states = ["NEW,ESTABLISHED", "ESTABLISHED", "NEW,ESTABLISHED", "ESTABLISHED"]
    additional = ["--syn", "--syn"]
    chain = "-I"

    if delete is True:
        chain = "-D"

    for parameter in range(0, 4):
        subprocess.Popen([
            "sudo",
            "iptables",
            "-t",
            "filter",
            chain,
            "FORWARD",
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
    ip_range = config.IP_RANGE_START + "-" + config.IP_RANGE_END
    chain = "-I"

    if delete is True:
        chain = "-D"

    subprocess.Popen([
        "sudo",
        "iptables",
        "-t",
        "filter",
        chain,
        "FORWARD",
        "-m",
        "iprange",
        "--src-range",
        ip_range,
        "-j",
        "DROP"
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.info("Applied unregistered users ACL")

def unlock_registered_device(ip_address):
    table = ["nat", "filter"]
    chain = ["PREROUTING", "FORWARD"]

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
    chain = ["PREROUTING", "FORWARD"]

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

