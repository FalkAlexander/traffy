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

import config as traffy_config
import dbus
import util
from pysnmp.entity import engine, config
from pysnmp.carrier.asyncore.dgram import udp
from pysnmp.entity.rfc3413 import ntfrcv
from pysnmp.proto.api import v2c


bus = dbus.SystemBus()
proxy = bus.get_object("uk.org.thekelleys.dnsmasq", "/uk/org/thekelleys/dnsmasq")
interface = dbus.Interface(proxy, dbus_interface="uk.org.thekelleys.dnsmasq")

def run_trap_listener():
    if not traffy_config.ENABLE_SNMP:
        print("SNMP not enabled! Exiting...")
        exit()

    if not traffy_config.ENABLE_TRAP:
        print("Trap not enabled! Exiting...")
        exit()

    snmp_engine = engine.SnmpEngine()
    config.addTransport(snmp_engine, udp.domainName, udp.UdpTransport().openServerMode(("0.0.0.0", traffy_config.TRAP_PORT)))

    for id in traffy_config.SWITCHES:
        config.addV3User(
            snmp_engine, traffy_config.SWITCHES[id]["username"],
            config.usmHMACSHAAuthProtocol, traffy_config.SWITCHES[id]["password"],
            config.usmDESPrivProtocol, traffy_config.SWITCHES[id]["password"],
            securityEngineId=v2c.OctetString(hexValue=traffy_config.SWITCHES[id]["engine_id"])
        )
    
    ntfrcv.NotificationReceiver(snmp_engine, trap_callback)
    snmp_engine.transportDispatcher.jobStarted(1)

    try:
        snmp_engine.transportDispatcher.runDispatcher()
    except:
        snmp_engine.transportDispatcher.closeDispatcher()


def trap_callback(snmp_engine, state_reference, context_engine_id, context_name, var_binds, cb_ctx):
    if not len(var_binds) >= 1:
        return

    if not len(var_binds[0]) >= 2:
        return

    if var_binds[1][0].prettyPrint() != "1.3.6.1.6.3.1.1.4.1.0" or var_binds[1][1].prettyPrint() != "1.3.6.1.6.3.1.1.5.3":
        return

    if var_binds[2][0].prettyPrint() != "1.3.6.1.2.1.2.2.1.1.1.0":
        return
    
    if var_binds[4][1].prettyPrint() != "2":
        return

    switch_name = context_engine_id.asOctets().decode("latin1")[5:]
    interface_name = util.parse_interface_name(var_binds[2][1].prettyPrint())
    search_text = "tag:" + switch_name + "_" + interface_name
    result_line = ""

    with open(traffy_config.ALLOCATION) as file:
        for line in file:
            line = line.rstrip()
            if search_text in line:
                result_line = line
                break

    if result_line != "":
        ip_address = result_line.split(",")[1]
        util.release(interface, ip_address)
        print("Released " + ip_address + " (" + switch_name + " / " + interface_name + ")")
