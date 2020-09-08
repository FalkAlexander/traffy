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

def setup_shaping():
    if config.STATELESS:
        return

    # Create root queueing disciplines
    for interface in config.LAN_INTERFACES:
        subprocess.Popen([
            "sudo",
            "tc",
            "qdisc",
            "add",
            "dev",
            interface,
            "handle",
            "1:",
            "root",
            "htb",
            "default",
            "0"
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    for ip in config.SHAPING_EXCEPTIONS:
        __add_shaping_exception_for_ip(ip)

    logging.info("Prepared traffic shaping queueing discipline")

def enable_shaping_for_ip(ip_id, ip_address):
    if config.STATELESS:
        return

    for interface in config.LAN_INTERFACES:
        # Create shaping class for ip
        subprocess.Popen([
            "sudo",
            "tc",
            "class",
            "add",
            "dev",
            interface,
            "parent",
            "1:1",
            "classid",
            "1:" + str(ip_id + 1),
            "htb",
            "rate",
            config.SHAPING_SPEED
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

        # Add matching filter to shaping class
        for direction in ["src", "dst"]:
            subprocess.Popen([
                "sudo",
                "tc",
                "filter",
                "add",
                "dev",
                interface,
                "protocol",
                "ip",
                "parent",
                "1:",
                "prio",
                "5",
                "u32",
                "match",
                "ip",
                direction,
                ip_address,
                "flowid",
                "1:" + str(ip_id + 1)
                ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.debug("Enabled traffic shaping for " + ip_address)

def disable_shaping_for_ip(ip_id, ip_address):
    if config.STATELESS:
        return

    for interface in config.LAN_INTERFACES:
        # Remove matching filter
        for handle in __get_rule_handles(interface, ip_address):
            subprocess.Popen([
                "sudo",
                "tc",
                "filter",
                "del",
                "dev",
                interface,
                "protocol",
                "ip",
                "parent",
                "1:",
                "handle",
                handle,
                "prio",
                "5",
                "u32"
                ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

        # Remove shaping class from ip
        subprocess.Popen([
            "sudo",
            "tc",
            "class",
            "del",
            "dev",
            interface,
            "parent",
            "1:1",
            "classid",
            "1:" + str(ip_id + 1)
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.debug("Disabled traffic shaping for " + ip_address)

def shutdown_shaping():
    if config.STATELESS:
        return

    for interface in config.LAN_INTERFACES:
        subprocess.Popen([
            "sudo",
            "tc",
            "qdisc",
            "del",
            "dev",
            interface,
            "root"
            ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.info("Removed traffic shaping queueing discipline")

#
# Private
#

def __add_shaping_exception_for_ip(ip_address): # ip _can_ contain decimal subnet mask: x.x.x.x/xx
    for direction in ["src", "dst"]:
        for interface in config.LAN_INTERFACES:
            subprocess.Popen([
                "sudo",
                "tc",
                "filter",
                "add",
                "dev",
                interface,
                "protocol",
                "ip",
                "parent",
                "1:",
                "prio",
                "1",
                "u32",
                "match",
                "ip",
                direction,
                ip_address,
                "flowid",
                "1:0"
                ], stdout=subprocess.PIPE, preexec_fn=os.setsid).wait()

    logging.debug("Traffic from/to " + ip_address + " excepted from shaping")

def __ip_to_hex_unsigned(ip_address):
    hex_str = ""
    for part in ip_address.split("."):
        hex_str += format((int(part)), "02x")

    return hex_str

def __get_rule_handles(device, ip_address):
    handles = []

    cmd = subprocess.Popen([
        "sudo",
        "tc",
        "filter",
        "show",
        "dev",
        device
        ], stdout=subprocess.PIPE)
    cmd.wait()

    out = cmd.communicate()[0].decode("utf-8")[:-1]
    split_lines = out.split("\n")
    result_lines = []
    count = 0
    for line in split_lines:
        if __ip_to_hex_unsigned(ip_address) in line:
            result_lines.append(count)
        count += 1

    if len(result_lines) == 0:
        return

    for line in result_lines:
        result = split_lines[line-1].split(" ")[11] # alternatively search for a block which contains ::
        handles.append(result)

    return handles

