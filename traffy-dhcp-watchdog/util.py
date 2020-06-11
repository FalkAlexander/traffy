import config
import os
import subprocess


def get_leases():
    leases = []
    with open(config.DNSMASQ_LEASE_FILE, "r") as lease_file:
        for line in lease_file:
            lease = line.split()
            leases.append([lease[1], lease[2]])
    
    return leases

def release(ip_address, mac_address):
    subprocess.Popen([
        "sudo",
        "dhcp_release",
        config.DHCP_INTERFACE,
        ip_address,
        mac_address
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

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
