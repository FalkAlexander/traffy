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


def get_mac_from_ip(ip_address):
    results = []
    with open(config.DNSMASQ_LEASE_FILE) as leases:
        for line in leases:
            elements = line.split()
            if len(elements) == 5:
                if elements[2] == ip_address:
                    results.append(elements[1])
    if results:
        return results[-1]
    else:
        return None


