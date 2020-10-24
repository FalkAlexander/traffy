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
import shlex


def setup_base_configuration():
    if config.STATELESS:
        return

    add_traffy_table()
    add_prerouting_chain()
    add_forward_chain()

def setup_captive_portal_configuration():
    if config.STATELESS:
        return
    
    add_captive_portal_chain()

    add_registered_set()

    insert_captive_portal_chain_forwarding_rules()
    add_unregistered_exception_accept_rules()
    add_captive_portal_rewrite_rules()
    add_unregistered_drop_rule()

def setup_accounting_configuration():
    if config.STATELESS:
        return

    add_accounting_chains()
    add_exceptions_set()

    add_ips_to_exceptions_set(config.ACCOUNTING_EXCEPTIONS)

    insert_accounting_chain_forwarding_rules()

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

# Captive Portal

def add_prerouting_chain():
    cmd = "add chain ip traffy prerouting { type nat hook prerouting priority - 100; }"
    __execute_command(cmd)

def add_captive_portal_chain():
    cmd = "add chain ip traffy captive-portal"
    __execute_command(cmd)

# Accounting

def add_forward_chain():
    cmd = "add chain ip traffy forward { type filter hook forward priority 0; }"
    __execute_command(cmd)

def add_accounting_chains():
    commands = []

    commands.append("add chain ip traffy accounting-ingress")
    commands.append("add chain ip traffy accounting-ingress-exc")

    commands.append("add chain ip traffy accounting-egress")
    commands.append("add chain ip traffy accounting-egress-exc")

    __execute_commands(commands)

#
# nftables sets
#

# Captive Portal

def add_registered_set():
    cmd = "add set ip traffy registered { type ipv4_addr; }"
    __execute_command(cmd)

def add_ip_to_registered_set(ip_address):
    cmd = "add element ip traffy registered { %s }" % ip_address
    __execute_command(cmd)

def add_ips_to_registered_set(ip_address_list):
    cmd = "add element ip traffy registered { %s }" % (", ".join(ip_address_list))
    __execute_command(cmd)

def delete_ip_from_registered_set(ip_address):
    cmd = "delete element ip traffy registered { %s }" % ip_address
    __execute_command(cmd)

def delete_ips_from_registered_set(ip_address_list):
    cmd = "delete element ip traffy registered { %s }" % (", ".join(ip_address_list))
    __execute_command(cmd)

# Accounting

def add_exceptions_set():
    cmd = "add set ip traffy exceptions { type ipv4_addr; flags interval; }"
    __execute_command(cmd)

def add_ips_to_exceptions_set(ip_address_list):
    cmd = "add element ip traffy exceptions { %s }" % (", ".join(ip_address_list))
    __execute_command(cmd)

def add_reg_key_set(reg_key_id):
    cmd = "add set ip traffy key-%s { type ipv4_addr; }" % reg_key_id
    __execute_command(cmd)

def add_ip_to_reg_key_set(ip_address, reg_key_id):
    cmd = "add element ip traffy key-%s { %s }" % (reg_key_id, ip_address)
    __execute_command(cmd)

def delete_reg_key_set(reg_key_id):
    cmd = "delete set traffy key-%s" % reg_key_id
    __execute_command(cmd)

#
# nftables rules
#

# Captive Portal

def insert_captive_portal_chain_forwarding_rules():
    cmd = "insert rule ip traffy prerouting ip saddr != @registered jump captive-portal"
    __execute_command(cmd)

def add_unregistered_exception_accept_rules():
    commands = []
    commands.append("add rule ip traffy captive-portal tcp dport 53 accept")
    commands.append("add rule ip traffy captive-portal udp dport 53 accept")
    commands.append("add rule ip traffy captive-portal udp dport 67 return")
    __execute_commands(commands)

def add_captive_portal_rewrite_rules():
    commands = []
    commands.append("add rule ip traffy captive-portal tcp dport { 80, 443 } dnat %s" % (config.WAN_IP_ADDRESS))
    __execute_commands(commands)

def add_unregistered_drop_rule():
    cmd = "add rule ip traffy captive-portal ip daddr != { %s, %s } drop" % (config.WAN_IP_ADDRESS, ", ".join([ip[1] for ip in config.IP_RANGES]))

    __execute_command(cmd)

# Accounting

def insert_accounting_chain_forwarding_rules():
    commands = []

    commands.append("insert rule ip traffy forward iif %s ip saddr != @exceptions jump accounting-ingress" % config.WAN_INTERFACE_ID)
    commands.append("insert rule ip traffy forward iif %s ip saddr @exceptions jump accounting-ingress-exc" % config.WAN_INTERFACE_ID)

    commands.append("insert rule ip traffy forward oif %s ip daddr != @exceptions jump accounting-egress" % config.WAN_INTERFACE_ID)
    commands.append("insert rule ip traffy forward oif %s ip daddr @exceptions jump accounting-egress-exc" % config.WAN_INTERFACE_ID)

    __execute_commands(commands)

def add_accounting_matching_rules(reg_key_id):
    add_accounting_counters(reg_key_id)

    commands = []

    commands.append("add rule ip traffy accounting-ingress ip daddr @key-%s counter name %s-ingress" % (reg_key_id, __digits_to_chars(reg_key_id)))
    commands.append("add rule ip traffy accounting-ingress-exc ip daddr @key-%s counter name %s-ingress-exc" % (reg_key_id, __digits_to_chars(reg_key_id)))

    commands.append("add rule ip traffy accounting-egress ip saddr @key-%s counter name %s-egress" % (reg_key_id, __digits_to_chars(reg_key_id)))
    commands.append("add rule ip traffy accounting-egress-exc ip saddr @key-%s counter name %s-egress-exc" % (reg_key_id, __digits_to_chars(reg_key_id)))

    __execute_commands(commands)

def delete_accounting_matching_rules(reg_key_id):
    chains = ["accounting-ingress", "accounting-ingress-exc", "accounting-egress", "accounting-egress-exc"]
    identifier = "@key-" + str(reg_key_id)

    for chain in chains:
        handles = __search_for_handles_in_chain(chain, identifier)

        for handle in handles:
            cmd = "delete rule traffy %s handle %s" % (chain, handle)
            __execute_command(cmd)
    
    delete_accounting_counters(reg_key_id)

#
# Generic command executor
#

def __execute_command(args):
    cmd = "sudo nft " + args
    cmd = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, preexec_fn=os.setsid)
    cmd.wait()

    return cmd

def __execute_commands(commands):
    for cmd in commands:
        __execute_command(cmd)

#
# nftables counters
#

def add_accounting_counters(reg_key_id):
    commands = []
    commands.append("add counter ip traffy %s-ingress packets 0 bytes 0" % __digits_to_chars(reg_key_id))
    commands.append("add counter ip traffy %s-ingress-exc packets 0 bytes 0" % __digits_to_chars(reg_key_id))

    commands.append("add counter ip traffy %s-egress packets 0 bytes 0" % __digits_to_chars(reg_key_id))
    commands.append("add counter ip traffy %s-egress-exc packets 0 bytes 0" % __digits_to_chars(reg_key_id))

    __execute_commands(commands)

def get_counter_values():
    cmd = "-j list counters table ip traffy"
    output = __execute_command(cmd).communicate()[0].decode("utf-8")
    tree = json.loads(output)

    counters = {}

    for array in tree["nftables"]:
        if "counter" not in array:
            continue

        if "bytes" not in array["counter"]:
            continue

        key_value = array["counter"]["name"]
        reg_key_id = __chars_to_digits(key_value.split("-", 1)[0]) + "-" + key_value.split("-", 1)[1]
        counter_value = array["counter"]["bytes"]

        counters[reg_key_id] = counter_value
    
    return counters

def reset_counter_values():
    cmd = "reset counters table ip traffy"
    __execute_command(cmd)

def delete_accounting_counters(reg_key_id):
    commands = []
    commands.append("delete counter traffy %s-ingress" % __digits_to_chars(reg_key_id))
    commands.append("delete counter traffy %s-ingress-exc" % __digits_to_chars(reg_key_id))

    commands.append("delete counter traffy %s-egress" % __digits_to_chars(reg_key_id))
    commands.append("delete counter traffy %s-egress-exc" % __digits_to_chars(reg_key_id))

    __execute_commands(commands)

#
# Util
#

def __digits_to_chars(integer):
    chr_value = ""
    for digit in list(str(integer)):
        chr_value += chr(int(digit) + 97)

    return chr_value

def __chars_to_digits(string):
    ord_value = ""
    for char in list(str(string)):
        ord_value += str(ord(char) - 97)
    
    return ord_value

def __search_for_handles_in_chain(chain_name, identifier):
    cmd = "list chain traffy %s -a" % chain_name
    output = __execute_command(cmd).communicate()[0].decode("utf-8")

    handles = []
    for line in output.splitlines():
        if not identifier in line:
            continue

        handle = line.split("handle ", 1)[1]
        handles.append(handle)
    
    return handles