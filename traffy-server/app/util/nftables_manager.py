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
    add_traffy_table()
    add_prerouting_chain()
    add_forward_chain()

def setup_captive_portal_configuration():    
    add_captive_portal_chain()
    add_registered_set()

def setup_advanced_captive_portal_configuration():
    add_captive_portal_chain_forwarding_rule()
    add_unregistered_exception_accept_rules()
    add_captive_portal_rewrite_rule()
    add_unregistered_drop_rule()

def setup_accounting_configuration():
    add_accounting_chains()
    add_exceptions_set()

    add_ips_to_exceptions_set(config.ACCOUNTING_EXCEPTIONS)

    add_accounting_chain_forwarding_rules()

#
# nftables tables
#

def add_traffy_table():
    __execute_command(
        "add table ip traffy"
    )

def delete_traffy_table():
    __execute_command(
        "delete table ip traffy"
    )

#
# nftables chains
#

# Captive Portal

def add_prerouting_chain():
    __execute_command(
        "add chain ip traffy prerouting { type nat hook prerouting priority - 100; }"
    )

def add_captive_portal_chain():
    __execute_command(
        "add chain ip traffy captive-portal"
    )

# Accounting

def add_forward_chain():
    __execute_command(
        "add chain ip traffy forward { type filter hook forward priority 0; }"
    )

def add_accounting_chains():
    __execute_commands([
        "add chain ip traffy accounting-ingress",
        "add chain ip traffy accounting-ingress-exc",
        "add chain ip traffy accounting-egress",
        "add chain ip traffy accounting-egress-exc"
    ])

#
# nftables sets
#

# Captive Portal

def add_registered_set():
    __execute_command(
        "add set ip traffy registered { type ether_addr . ipv4_addr; }"
    )

def add_allocation_to_registered_set(mac_address, ip_address):
    __execute_command(
        "add element ip traffy registered { %s }" % (mac_address + " . " + ip_address)
    )

def add_allocations_to_registered_set(allocation_list):
    __execute_command(
        "add element ip traffy registered { %s }" % ", ".join([mac + " . " + ip for mac, ip in allocation_list.items()])
    )

def delete_allocation_from_registered_set(mac_address, ip_address):
    __execute_command(
        "delete element ip traffy registered { %s }" % (mac_address + " . " + ip_address)
    )

def delete_allocations_from_registered_set(allocation_list):
    __execute_command(
        "delete element ip traffy registered { %s }" % ", ".join([mac + " . " + ip for mac, ip in allocation_list.items()])
    )

# Accounting

def add_exceptions_set():
    __execute_command(
        "add set ip traffy exceptions { type ipv4_addr; flags interval; }"
    )

def add_ips_to_exceptions_set(ip_address_list):
    __execute_command(
        "add element ip traffy exceptions { %s }" % (", ".join(ip_address_list))
    )

def add_reg_key_set(reg_key_id):
    __execute_command(
        "add set ip traffy key-%s { type ipv4_addr; }" % reg_key_id
    )

def add_ip_to_reg_key_set(ip_address, reg_key_id):
    __execute_command(
        "add element ip traffy key-%s { %s }" % (reg_key_id, ip_address)
    )

def delete_ip_from_reg_key_set(ip_address, reg_key_id):
    __execute_command(
        "delete element ip traffy key-%s { %s }" % (reg_key_id, ip_address)
    )

def delete_reg_key_set(reg_key_id):
    __execute_command(
        "delete set traffy key-%s" % reg_key_id
    )

#
# nftables rules
#

# Captive Portal

def add_captive_portal_chain_forwarding_rule():
    __execute_command(
        "add rule ip traffy prerouting iif { %s } ether saddr . ip saddr != @registered goto captive-portal" % ", ".join([ip[4] for ip in config.IP_RANGES])
    )

def add_unregistered_exception_accept_rules():
    __execute_commands([
        "add rule ip traffy captive-portal tcp dport 53 accept",
        "add rule ip traffy captive-portal udp dport vmap { 53 : accept, 67 : return }"
    ])

def add_captive_portal_rewrite_rule():
    __execute_command(
        "add rule ip traffy captive-portal tcp dport { 80, 443 } dnat %s" % (config.WAN_IP_ADDRESS)
    )

def add_unregistered_drop_rule():
    __execute_command(
        "add rule ip traffy captive-portal ip daddr != { %s, %s } drop" % (config.WAN_IP_ADDRESS, ", ".join([ip[1] for ip in config.IP_RANGES]))
    )


# Accounting

def add_accounting_chain_forwarding_rules():
    __execute_commands([
        "add rule ip traffy forward iif %s ip saddr != @exceptions goto accounting-ingress" % config.WAN_INTERFACE_ID,
        "add rule ip traffy forward iif %s ip saddr @exceptions goto accounting-ingress-exc" % config.WAN_INTERFACE_ID,
        "add rule ip traffy forward oif %s ip daddr != @exceptions goto accounting-egress" % config.WAN_INTERFACE_ID,
        "add rule ip traffy forward oif %s ip daddr @exceptions goto accounting-egress-exc" % config.WAN_INTERFACE_ID
    ])

def add_accounting_matching_rules(reg_key_id):
    add_accounting_counters(reg_key_id)

    __execute_commands([
        "add rule ip traffy accounting-ingress ip daddr @key-%s counter name %s-ingress" % (reg_key_id, __digits_to_chars(reg_key_id)),
        "add rule ip traffy accounting-ingress-exc ip daddr @key-%s counter name %s-ingress-exc" % (reg_key_id, __digits_to_chars(reg_key_id)),
        "add rule ip traffy accounting-egress ip saddr @key-%s counter name %s-egress" % (reg_key_id, __digits_to_chars(reg_key_id)),
        "add rule ip traffy accounting-egress-exc ip saddr @key-%s counter name %s-egress-exc" % (reg_key_id, __digits_to_chars(reg_key_id))
    ])

def delete_accounting_matching_rules(reg_key_id):
    chains = ["accounting-ingress", "accounting-ingress-exc", "accounting-egress", "accounting-egress-exc"]
    identifier = "@key-" + str(reg_key_id) + " "

    for chain in chains:
        handles = __search_for_handles_in_chain(chain, identifier)

        for handle in handles:
            __execute_command("delete rule traffy %s handle %s" % (chain, handle))
    
    delete_accounting_counters(reg_key_id)

#
# Generic command executor
#

def __execute_command(args, output=False):
    cmd = "sudo nft " + args

    if output is True:
        proc = subprocess.run(shlex.split(cmd), capture_output=True, text=True, encoding="utf-8")
        return proc.stdout
    else:
        proc = subprocess.run(shlex.split(cmd), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc

def __execute_commands(commands):
    for cmd in commands:
        __execute_command(cmd)

#
# nftables counters
#

def add_accounting_counters(reg_key_id):
    __execute_commands([
        "add counter ip traffy %s-ingress packets 0 bytes 0" % __digits_to_chars(reg_key_id),
        "add counter ip traffy %s-ingress-exc packets 0 bytes 0" % __digits_to_chars(reg_key_id),
        "add counter ip traffy %s-egress packets 0 bytes 0" % __digits_to_chars(reg_key_id),
        "add counter ip traffy %s-egress-exc packets 0 bytes 0" % __digits_to_chars(reg_key_id)
    ])

def get_counter_values():
    cmd = "-j list counters table ip traffy"
    output = __execute_command(cmd, output=True)
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
    __execute_command(
        "reset counters table ip traffy"
    )

def delete_accounting_counters(reg_key_id):
    __execute_commands([
        "delete counter traffy %s-ingress" % __digits_to_chars(reg_key_id),
        "delete counter traffy %s-ingress-exc" % __digits_to_chars(reg_key_id),
        "delete counter traffy %s-egress" % __digits_to_chars(reg_key_id),
        "delete counter traffy %s-egress-exc" % __digits_to_chars(reg_key_id)
    ])

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
    output = __execute_command(cmd, output=True)

    handles = []
    for line in output.splitlines():
        if not identifier in line:
            continue

        handle = line.split("handle ", 1)[1]
        handles.append(handle)
    
    return handles