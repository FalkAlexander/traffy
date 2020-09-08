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


def create_box(reg_key, delete=False):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    names = [reg_key + "-INGRESS", reg_key + "-EGRESS", reg_key + "-INGRESS-EXC", reg_key + "-EGRESS-EXC"]
    action = "-N"

    if delete is True:
        action = "-X"
        destroy_ipset(reg_key)
    else:
        create_ipset(reg_key)
        for exc_ip in config.SHAPING_EXCEPTIONS:
            add_ipset_ip(reg_key, exc_ip)

    for name in names:
        subprocess.Popen([
            "sudo",
            "iptables",
            action,
            name
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

def create_box_route(reg_key, delete=False):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    names = [reg_key + "-INGRESS", reg_key + "-EGRESS", reg_key + "-INGRESS-EXC", reg_key + "-EGRESS-EXC"]
    action = "-I"

    if delete is True:
        action = "-D"

    for name in names:
        subprocess.Popen([
            "sudo",
            "iptables",
            action,
            "FORWARD",
            "-j",
            name
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

def attach_traffic_to_box(reg_key, delete=False):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    names_ingress = [reg_key + "-INGRESS", reg_key + "-INGRESS-EXC"]
    names_egress = [reg_key + "-EGRESS", reg_key + "-EGRESS-EXC"]
    action = "-I"

    if delete is True:
        action = "-D"

    for name_ingress in names_ingress:
        subprocess.Popen([
            "sudo",
            "iptables",
            action,
            "INPUT",
            "-j",
            name_ingress
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    for name_egress in names_egress:
        subprocess.Popen([
            "sudo",
            "iptables",
            action,
            "OUTPUT",
            "-j",
            name_egress
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

def add_ip_to_box(reg_key, ip_address):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    name_ingress = reg_key + "-INGRESS"
    name_egress = reg_key + "-EGRESS"

    subprocess.Popen([
        "sudo",
        "iptables",
        "-I",
        name_ingress,
        "-d",
        ip_address
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    subprocess.Popen([
        "sudo",
        "iptables",
        "-I",
        name_egress,
        "-s",
        ip_address
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    add_exception_box_ips(reg_key, ip_address)

def remove_ip_from_box(reg_key, ip_address):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    name_ingress = reg_key + "-INGRESS"
    name_egress = reg_key + "-EGRESS"
    ip = ip_address + "/32"

    subprocess.Popen([
        "sudo",
        "iptables",
        "-D",
        name_ingress,
        "-d",
        ip
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    subprocess.Popen([
        "sudo",
        "iptables",
        "-D",
        name_egress,
        "-s",
        ip
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    remove_exception_box_ips(reg_key, ip_address)

def get_box_ingress_bytes(reg_key):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    name = reg_key + "-INGRESS"
    cmd = subprocess.Popen([
        "sudo",
        "iptables",
        "-v",
        "-n",
        "-x",
        "-L",
        name
        ], stdout=subprocess.PIPE)
    cmd.wait()

    return parse_iptables_output(cmd) - get_exception_box_ingress_bytes(reg_key)

def get_box_egress_bytes(reg_key):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    name = reg_key + "-EGRESS"
    cmd = subprocess.Popen([
        "sudo",
        "iptables",
        "-v",
        "-n",
        "-x",
        "-L",
        name
        ], stdout=subprocess.PIPE)
    cmd.wait()

    return parse_iptables_output(cmd) - get_exception_box_egress_bytes(reg_key)

def reset_box_counter(reg_key):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    names = [reg_key + "-INGRESS", reg_key + "-EGRESS", reg_key + "-INGRESS-EXC", reg_key + "-EGRESS-EXC"]

    for name in names:
        subprocess.Popen([
            "sudo",
            "iptables",
            "-L",
            name,
            "-Z"
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

# For from Accounting Excepted Traffic

def add_exception_box_ips(reg_key, ip_address):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    name_ingress = reg_key + "-INGRESS-EXC"
    name_egress = reg_key + "-EGRESS-EXC"

    subprocess.Popen([
        "sudo",
        "iptables",
        "-I",
        name_ingress,
        "-d",
        ip_address,
        "-m",
        "set",
        "--match-set",
        reg_key,
        "src"
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    subprocess.Popen([
        "sudo",
        "iptables",
        "-I",
        name_egress,
        "-m",
        "set",
        "--match-set",
        reg_key,
        "dst",
        "-s",
        ip_address
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

def remove_exception_box_ips(reg_key, ip_address):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    name_ingress = reg_key + "-INGRESS-EXC"
    name_egress = reg_key + "-EGRESS-EXC"

    subprocess.Popen([
        "sudo",
        "iptables",
        "-D",
        name_ingress,
        "-d",
        ip_address,
        "-m",
        "set",
        "--match-set",
        reg_key,
        "src"
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    subprocess.Popen([
        "sudo",
        "iptables",
        "-D",
        name_egress,
        "-m",
        "set",
        "--match-set",
        reg_key,
        "dst",
        "-s",
        ip_address
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

def get_exception_box_ingress_bytes(reg_key):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    name = reg_key + "-INGRESS-EXC"
    cmd = subprocess.Popen([
        "sudo",
        "iptables",
        "-v",
        "-n",
        "-x",
        "-L",
        name
        ], stdout=subprocess.PIPE)
    cmd.wait()

    return parse_iptables_output(cmd)

def get_exception_box_egress_bytes(reg_key):
    if config.STATELESS:
        return

    reg_key = str(reg_key)
    name = reg_key + "-EGRESS-EXC"
    cmd = subprocess.Popen([
        "sudo",
        "iptables",
        "-v",
        "-n",
        "-x",
        "-L",
        name
        ], stdout=subprocess.PIPE)
    cmd.wait()

    return parse_iptables_output(cmd)

# General

def add_accounter_chain(reg_key):
    create_box(reg_key)
    create_box_route(reg_key)
    attach_traffic_to_box(reg_key)
    logging.debug("Added accounting rules for key " + str(reg_key))

def remove_accounter_chain(reg_key):
    attach_traffic_to_box(reg_key, delete=True)
    create_box_route(reg_key, delete=True)
    create_box(reg_key, delete=True)
    logging.debug("Removed accounting rules for key " + str(reg_key))

# Util

def parse_iptables_output(cmd):
    out = cmd.communicate()[0].decode("utf-8")
    if len(out.splitlines()) == 0:
        return 0
    else:
        bytes = [column.split()[1] for column in out.splitlines()][2:]
        traffic = 0
        for element in bytes:
            traffic += int(element)
        return traffic

def create_ipset(reg_key):
    if config.STATELESS:
        return

    cmd = subprocess.Popen([
        "sudo",
        "ipset",
        "create",
        reg_key,
        "hash:net"
        ], stdout=subprocess.PIPE)
    cmd.wait()

def add_ipset_ip(reg_key, ip_address):
    if config.STATELESS:
        return

    cmd = subprocess.Popen([
        "sudo",
        "ipset",
        "add",
        reg_key,
        ip_address
        ], stdout=subprocess.PIPE)
    cmd.wait()

def destroy_ipset(reg_key):
    if config.STATELESS:
        return

    cmd = subprocess.Popen([
        "sudo",
        "ipset",
        "destroy",
        reg_key
        ], stdout=subprocess.PIPE)
    cmd.wait()

