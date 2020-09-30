"""
 Copyright (C) 2020 Niklas Merkelt <niklasmerkelt@mail.de>

 Author: Niklas Merkelt <niklasmerkelt@mail.de>

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
import subprocess


def create_ipset(name):
    if config.STATELESS:
        return

    cmd = subprocess.Popen([
        "sudo",
        "ipset",
        "create",
        name,
        "hash:net"
        ], stdout=subprocess.PIPE)
    cmd.wait()


def add_ipset_ip(name, ip_net):
    if config.STATELESS:
        return

    cmd = subprocess.Popen([
        "sudo",
        "ipset",
        "add",
        name,
        ip_net
        ], stdout=subprocess.PIPE)
    cmd.wait()


def destroy_ipset(name):
    if config.STATELESS:
        return

    cmd = subprocess.Popen([
        "sudo",
        "ipset",
        "destroy",
        name
        ], stdout=subprocess.PIPE)
    cmd.wait()
