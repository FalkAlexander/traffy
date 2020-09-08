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

import subprocess
import os
import logging


#
# IP and MAC Spoofing Protection
#

def add_static_arp_entry(ip_address, mac_address):
    if config.STATELESS:
        return

    subprocess.Popen([
        "sudo",
        "arp",
        "-s",
        ip_address,
        mac_address
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid)

    logging.debug("Started IP spoofing protection for " + ip_address)

def remove_static_arp_entry(ip_address):
    if config.STATELESS:
        return
    
    subprocess.Popen([
        "sudo",
        "arp",
        "-d",
        ip_address
        ], stdout=subprocess.PIPE, preexec_fn=os.setsid)

    logging.debug("Stopped IP spoofing protection for " + ip_address)

