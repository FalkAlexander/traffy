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
import logging
import os
import shlex
import subprocess


#
# tc htb queue handling
#

# Create root queueing discipline

def setup_shaping():
    for interface in config.LAN_INTERFACES:
        __execute_command(
            "qdisc add dev %s handle 1: root htb default 0" % interface
        )

    for ip in config.SHAPING_EXCEPTIONS:
        __add_shaping_exception_for_ip(ip)

    logging.info("Prepared traffic shaping queueing discipline")

# Create shaping class for ip and add matching filters

def enable_shaping_for_ip(ip_id, ip_address):
    for interface in config.LAN_INTERFACES:
        
        __execute_command(
            "class add dev %s parent 1:1 classid 1:%s htb rate %s" % (interface, str(ip_id + 1), config.SHAPING_SPEED)
        )

        for direction in ["src", "dst"]:
            __execute_command(
                "filter add dev %s protocol ip parent 1: prio 5 u32 match ip %s %s flowid 1:%s" % (interface, direction, ip_address, str(ip_id + 1))
            )

    logging.debug("Enabled traffic shaping for " + ip_address)

# Delete shaping class with its belonging filters

def disable_shaping_for_ip(ip_id, ip_address):
    for interface in config.LAN_INTERFACES:
        for handle in __get_rule_handles(interface, ip_address):
            __execute_command(
                "filter del dev %s protocol ip parent 1: handle %s prio 5 u32" % (interface, handle)
            )

        __execute_command(
            "class del dev %s parent 1:1 classid 1:%s" % (interface, str(ip_id + 1))
        )

    logging.debug("Disabled traffic shaping for " + ip_address)

# Delete root queueing discipline

def shutdown_shaping():
    for interface in config.LAN_INTERFACES:
        __execute_command(
            "qdisc del dev %s root" % interface
        )

    logging.info("Removed traffic shaping queueing discipline")

#
# Private
#

def __add_shaping_exception_for_ip(ip_address): # ip _can_ contain decimal subnet mask: x.x.x.x/xx
    for direction in ["src", "dst"]:
        for interface in config.LAN_INTERFACES:
            __execute_command(
                "filter add dev %s protocol ip parent 1: prio 1 u32 match ip %s %s flowid 1:0" % (interface, direction, ip_address)
            )

    logging.debug("Traffic from/to " + ip_address + " excepted from shaping")

def __ip_to_hex_unsigned(ip_address):
    hex_str = ""
    for part in ip_address.split("."):
        hex_str += format((int(part)), "02x")

    return hex_str

def __get_rule_handles(device, ip_address):
    handles = []

    output = __execute_command("filter show dev %s" % device, output=True)
    split_lines = output.split("\n")
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

#
# Generic command executor
#

def __execute_command(args, output=False):
    cmd = "tc " + args

    if output is True:
        proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True, encoding="utf-8")
        return proc.stdout
    else:
        proc = subprocess.run(shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc
