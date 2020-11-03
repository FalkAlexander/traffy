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
import threading
import trap_listener
import util


def response_check(ip_address, mac_address):
    if config.ENABLE_SNMP:
        if interfaces_status_list.get(ip_address) != "2":
            return
    else:
        if util.arping(ip_address) is True:
            return

    if ip_address not in config.EXCLUDED_IPS:
        util.release(interface, ip_address)
        print("Released " + ip_address + " / " + mac_address)
    else:
        print("Excluded Release Event: " + ip_address + " / " + mac_address)

if config.ENABLE_SNMP and config.ENABLE_TRAP:
    trap_listener.run_trap_listener()
else:
    bus = dbus.SystemBus()
    proxy = bus.get_object("uk.org.thekelleys.dnsmasq", "/uk/org/thekelleys/dnsmasq")
    interface = dbus.Interface(proxy, dbus_interface="uk.org.thekelleys.dnsmasq")

    leases = util.get_leases()
    if config.ENABLE_SNMP:
        interfaces_status_list = util.query_interfaces_status()

    for lease in leases:
        ip_address = lease[1]
        mac_address = lease[0]

        if config.ENABLE_SNMP:
            response_check(ip_address, mac_address)
        else:
            resp_thread = threading.Thread(target=response_check, args=(ip_address, mac_address))
            resp_thread.start()
