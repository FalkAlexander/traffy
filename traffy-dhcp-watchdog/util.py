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
import dbus
import subprocess


def get_leases():
    leases = []
    with open(config.DNSMASQ_LEASE_FILE, "r") as lease_file:
        for line in lease_file:
            lease = line.split()
            leases.append([lease[1], lease[2]])
    
    return leases

def release(dbus_interface, ip_address):
    dbus_interface.DeleteDhcpLease(dbus.String(ip_address))

def arping(ip_address):
    proc = subprocess.Popen([
            "arping",
            ip_address,
            "-c",
            str(config.PING_TRIES)
            ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    proc.wait()
    stdout = proc.communicate()[0].decode("utf-8")

    if "100% unanswered" in stdout:
        return False
    else:
        return True
