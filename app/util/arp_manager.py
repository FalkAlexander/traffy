import subprocess
import os
import logging


#
# IP and MAC Spoofing Protection
#

def add_static_arp_entry(ip_address, mac_address):
    subprocess.Popen([
        "sudo",
        "arp",
        "-s",
        ip_address,
        mac_address
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid)

    logging.debug("Started IP spoofing protection for " + ip_address)

def remove_static_arp_entry(ip_address):
    subprocess.Popen([
        "sudo",
        "arp",
        "-d",
        ip_address
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid)

    logging.debug("Stopped IP spoofing protection for " + ip_address)

