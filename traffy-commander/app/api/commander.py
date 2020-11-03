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

from app import nftables_manager as nft
from app import tc_manager as tc


class CommanderAPI:
    def setup_advanced_captive_portal_configuration(self):
        self.add_captive_portal_chain_forwarding_rule()
        self.add_unregistered_exception_accept_rules()
        self.add_captive_portal_rewrite_rule()
        self.add_unregistered_drop_rule()

    def add_traffy_table(self):
        nft.add_traffy_table()

    def delete_traffy_table(self):
        nft.delete_traffy_table()

    #
    # nftables chains
    #

    # Captive Portal

    def add_prerouting_chain(self):
        nft.add_prerouting_chain()

    def add_captive_portal_chain(self):
        nft.add_captive_portal_chain()

    # Accounting

    def add_forward_chain(self):
        nft.add_forward_chain()

    def add_accounting_chains(self):
        nft.add_accounting_chains()

    #
    # nftables sets
    #

    # Captive Portal

    def add_registered_set(self):
        nft.add_registered_set()

    def add_allocation_to_registered_set(self, mac_address, ip_address):
        nft.add_allocation_to_registered_set(mac_address, ip_address)

    def add_allocations_to_registered_set(self, allocation_list):
        nft.add_allocations_to_registered_set(allocation_list)

    def delete_allocation_from_registered_set(self, mac_address, ip_address):
        nft.delete_allocation_from_registered_set(mac_address, ip_address)

    def delete_allocations_from_registered_set(self, allocation_list):
        nft.delete_allocations_from_registered_set(allocation_list)

    # Accounting

    def add_exceptions_set(self):
        nft.add_exceptions_set()

    def add_ips_to_exceptions_set(self, ip_address_list):
        nft.add_ips_to_exceptions_set(ip_address_list)

    def add_reg_key_set(self, reg_key_id):
        nft.add_reg_key_set(reg_key_id)

    def add_ip_to_reg_key_set(self, ip_address, reg_key_id):
        nft.add_ip_to_reg_key_set(ip_address, reg_key_id)

    def delete_ip_from_reg_key_set(self, ip_address, reg_key_id):
        nft.delete_ip_from_reg_key_set(ip_address, reg_key_id)

    def delete_reg_key_set(self, reg_key_id):
        nft.delete_reg_key_set(reg_key_id)

    #
    # nftables rules
    #

    # Captive Portal

    def add_captive_portal_chain_forwarding_rule(self):
        nft.add_captive_portal_chain_forwarding_rule()

    def add_unregistered_exception_accept_rules(self):
        nft.add_unregistered_exception_accept_rules()

    def add_captive_portal_rewrite_rule(self):
        nft.add_captive_portal_rewrite_rule()

    def add_unregistered_drop_rule(self):
        nft.add_unregistered_drop_rule()


    # Accounting

    def add_accounting_chain_forwarding_rules(self):
        nft.add_accounting_chain_forwarding_rules()

    def add_accounting_matching_rules(self, reg_key_id):
        nft.add_accounting_matching_rules(reg_key_id)

    def delete_accounting_matching_rules(self, reg_key_id):
        nft.delete_accounting_matching_rules(reg_key_id)

    #
    # nftables counters
    #

    def add_accounting_counters(self, reg_key_id):
        nft.add_accounting_counters(reg_key_id)

    def get_counter_values(self):
        return nft.get_counter_values()

    def reset_counter_values(self):
        nft.reset_counter_values()

    def delete_accounting_counters(self, reg_key_id):
        nft.delete_accounting_counters(reg_key_id)

    #
    # tc htb queue handling
    #

    # Create root queueing discipline

    def setup_shaping(self):
        tc.setup_shaping()

    # Create shaping class for ip and add matching filters

    def enable_shaping_for_ip(self, ip_id, ip_address):
        tc.enable_shaping_for_ip(ip_id, ip_address)

    # Delete shaping class with its belonging filters

    def disable_shaping_for_ip(self, ip_id, ip_address):
        tc.disable_shaping_for_ip(ip_id, ip_address)

    # Delete root queueing discipline

    def shutdown_shaping(self):
        tc.shutdown_shaping()
