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
from easysnmp import Session


def parse_interface_name(value):
    if len(value) == 4:
        switch = "1"
        slot = value[0]
        if value[2] == "0":
            port = value[3]
        else:     
            port = value[2:]
        return switch + "-" + slot + "-" + port
    elif len(value) == 6:
        switch = str(int(value[0]) + 1)
        slot = value[2]
        if value[4] == "0":     
            port = value[5]
        else:
            port = value[4:]
        return switch + "-" + slot + "-" + port
    else:
        return value

def query_interfaces_status():
    interface_dict = {}
    for id in config.SWITCHES:
        switch_name = config.SWITCHES[id]["name"]
        hostname = config.SWITCHES[id]["hostname"]
        username = config.SWITCHES[id]["username"]
        password = config.SWITCHES[id]["password"]

        session = Session(hostname=hostname,
                        security_level=u"auth_with_privacy",
                        security_username=username,
                        auth_protocol=u"SHA",
                        auth_password=password,
                        privacy_password=password,
                        version=3)

        interfaces_status = session.walk("1.3.6.1.2.1.2.2.1.8")

        for item in interfaces_status:
            search_text = "tag:" + switch_name + "_" + parse_interface_name(item.oid.replace("iso.3.6.1.2.1.2.2.1.8.", ""))
            result_line = ""
            with open(config.ALLOCATION) as file:
                for line in file:
                    line = line.rstrip()
                    if search_text in line:
                        result_line = line
                        break

            if result_line != "":
                port_ip_address = result_line.split(",")[1]
                interface_dict[port_ip_address] = item.value
    
    return interface_dict

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
