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
import shlex


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

    for cmd in commands:
        __execute_command(cmd)

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

    for cmd in commands:
        __execute_command(cmd)

#
# Generic command executor
#

def __execute_command(args):
    cmd = "sudo nft " + args
    cmd = subprocess.Popen(shlex.split(cmd), stdout=subprocess.PIPE, preexec_fn=os.setsid))
    cmd.wait()

    return cmd