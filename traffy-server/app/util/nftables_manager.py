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
import json
import os
import subprocess
import logging
import shlex
import re


def setup_traffy_base_configuration():
    if config.STATELESS:
        return

    add_traffy_table()
    add_forward_chain()

    add_exceptions_set()
    add_accounting_chains()

#
# nftables tables
#

def add_traffy_table():
    cmd = "add table ip traffy"
    __execute_command(cmd)

def delete_traffy_table():
    cmd = "delete table ip traffy"
    __execute_command(cmd)

#
# nftables chains
#

def add_forward_chain():
    cmd = "add chain ip traffy forward { type filter hook forward priority 0; }"
    __execute_command(cmd)

def add_accounting_chains():
    commands = []

    commands.append("add chain ip traffy acc-ingress")
    commands.append("add chain ip traffy acc-ingress-exc")

    commands.append("add chain ip traffy acc-egress")
    commands.append("add chain ip traffy acc-egress-exc")

    __execute_commands(commands)

#
# nftables sets
#

def add_exceptions_set():
    cmd = "add set ip traffy exceptions { type ipv4_addr; }"
    __execute_command(cmd)

def add_reg_key_set(reg_key_id):
    cmd = "add set ip traffy key-%s { type ipv4_addr; }" % reg_key_id
    __execute_command(cmd)

def add_ips_to_reg_key_set(ip_address_list, reg_key_id):
    cmd = "add element ip traffy key-%s { %s }" % (reg_key_id, ", ".join(ip_address_list))
    __execute_command(cmd)

#
# nftables rules
#

def insert_accounting_chain_forwarding_rules():
    commands = []

    commands.append("insert rule ip traffy forward iifname %s ip saddr != @exceptions jump acc-ingress" % config.WAN_INTERFACE)
    commands.append("insert rule ip traffy forward iifname %s ip saddr = @exceptions jump acc-ingress-exc" % config.WAN_INTERFACE)

    commands.append("insert rule ip traffy forward oifname %s ip daddr != @exceptions jump acc-egress" % config.WAN_INTERFACE)
    commands.append("insert rule ip traffy forward oifname %s ip daddr = @exceptions jump acc-egress-exc" % config.WAN_INTERFACE)

    __execute_commands(commands)

def add_accounting_matching_rules(reg_key_id):
    add_counter(reg_key_id)

    commands = []

    commands.append("add rule ip traffy acc-ingress ip daddr @key-%s counter name %s-ingress" % (reg_key_id, reg_key_id))
    commands.append("add rule ip traffy acc-ingress-exc ip daddr @key-%s counter name %s-ingress-exc" % (reg_key_id, reg_key_id))

    commands.append("add rule ip traffy acc-egress ip saddr @key-%s counter name %s-egress" % (reg_key_id, reg_key_id))
    commands.append("add rule ip traffy acc-egress-exc ip saddr @key-%s counter name %s-egress-exc" % (reg_key_id, reg_key_id))

    __execute_commands(commands)

#
# Generic command executor
#

def __execute_command(args):
    cmd = "sudo nft " + args
    cmd = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, preexec_fn=os.setsid))
    cmd.wait()

    return cmd

def __execute_commands(commands):
    for cmd in commands:
        __execute_command(cmd)

#
# nftables counters
#

def add_ingress_counters(reg_key_id):
    commands = []
    commands.append("add counter ip traffy %s-ingress packets 0 bytes 0" % reg_key_id)
    commands.append("add counter ip traffy %s-ingress-exc packets 0 bytes 0" % reg_key_id)
    __execute_commands(commands)

def add_egress_counters(reg_key_id):
    commands = []
    commands.append("add counter ip traffy %s-egress packets 0 bytes 0" % reg_key_id)
    commands.append("add counter ip traffy %s-egress-exc packets 0 bytes 0" % reg_key_id)
    __execute_commands(commands)

def get_counter_values():
    cmd = "-j list counters table ip traffy"
    output = __execute_command(cmd).communicate()[0].decode("utf-8")
    tree = json.loads(output)

    counters = {}
    strip_letters = re.compile(r'\d+(?:\.\d+)?')

    for array in data["nftables"]:
        if "counter" not in array:
            continue

        if "bytes" not in array["counter"]:
            continue

        reg_key_id = strip_letters.findall(array["counter"]["name"])[0]
        counter_value = array["counter"]["bytes"]

        counters[reg_key_id] = counter_value
    
    return counters

def reset_counter_values():
    cmd = "reset counters table ip traffy"
    __execute_command(cmd)