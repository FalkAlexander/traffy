"""
 Copyright (C) 2020 Falk Seidl <hi@falsei.de>
 
 Author: Falk Seidl <hi@falsei.de>
 
 This program is free software; you can redistribute it and/or
 modify it under the terms of the GNU General Public License as
 published by the Free Software Foundation; either version 2 of the
 License, or (at your option) any later version.
 
 This program is distributed in the hope that it will be useful, but
 WITHOUT ANY WARRANTY; without even the implied warranty of
 MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 General Public License for more details.
 
 You should have received a copy of the GNU General Public License
 along with this program; if not, see <http://www.gnu.org/licenses/>.
"""

import config
import os
import subprocess
import logging


def apply_redirect_rule(delete=False):
    if config.STATELESS:
        return

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
    if config.STATELESS:
        return

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
    if config.STATELESS:
        return

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
    if config.STATELESS:
        return

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
    if config.STATELESS:
        return

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
                "-j",
                "ACCEPT"
                ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.info("Applied DNS tunnel protection")

def apply_block_rule(delete=False):
    if config.STATELESS:
        return

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
    if config.STATELESS:
        return

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
    if config.STATELESS:
        return

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

