from .. import db, accounting_srv, dnsmasq_srv
from ..models import AddressPair, RegistrationKey, IpAddress, MacAddress, Traffic, Identity
from ..util import arp_manager, iptables_accounting_manager, iptables_rules_manager, lease_parser, dnsmasq_manager, shaping_manager
import datetime


def register_device(input_key, ip_address, request):
    # Rahmennetzordnung
    reg_key_query = RegistrationKey.query.filter_by(key=input_key).first()
    reg_key_query.eula_accepted = True

    # IP Entry
    ip_address_query = IpAddress.query.filter_by(address_v4=ip_address).first()
    if ip_address_query is None:
        db.session.add(IpAddress(address_v4=ip_address, address_v6=None))
    else:
        flash(_l("Error during registration.") + " Code: 120")
        raise RegistrationError

    # MAC Entry
    mac_address = lease_parser.get_mac_from_ip(ip_address)
    if mac_address is None:
        flash(_l("Error during registration.") + " Code: 125")
        raise RegistrationError
    mac_address_query = MacAddress.query.filter_by(address=mac_address).first()
    if mac_address_query is None:
        user_agent_string = request.headers.get("User-Agent")
        if len(user_agent_string) > 500:
            user_agent_string = ""

        db.session.add(MacAddress(address=mac_address, user_agent=user_agent_string, first_known_since=datetime.datetime.now()))
    else:
        flash(_l("Error during registration.") + " Code: 130")
        raise RegistrationError

    # Create AddressPair
    mac_address_query = MacAddress.query.filter_by(address=mac_address).first()
    ip_address_query = IpAddress.query.filter_by(address_v4=ip_address).first()
    db.session.add(AddressPair(reg_key=reg_key_query.id, mac_address=mac_address_query.id, ip_address=ip_address_query.id))

    # Write DB
    db.session.commit()

    dnsmasq_manager.add_static_lease(mac_address, ip_address)
    dnsmasq_srv.reload()

    # Setup Firewall
    iptables_rules_manager.unlock_registered_device(ip_address)

    # Setup Accounting
    if AddressPair.query.filter_by(reg_key=reg_key_query.id).count() <= 1:
        iptables_accounting_manager.add_accounter_chain(reg_key_query.id)
        iptables_accounting_manager.add_ip_to_box(reg_key_query.id, ip_address)
    else:
        iptables_accounting_manager.add_ip_to_box(reg_key_query.id, ip_address)

    # Spoofing Protection
    arp_manager.add_static_arp_entry(ip_address, mac_address)

    # Setup Shaping
    if reg_key_query.id in accounting_srv.shaped_reg_keys:
        shaping_manager.enable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

def deregister_device(ip_address):
    mac_address = lease_parser.get_mac_from_ip(ip_address)

    ip_address_query = IpAddress.query.filter_by(address_v4=ip_address).first()
    mac_address_query = MacAddress.query.filter_by(address=mac_address).first()
    address_pair_query = AddressPair.query.filter_by(mac_address=mac_address_query.id, ip_address=ip_address_query.id).first()
    reg_key_query = RegistrationKey.query.filter_by(id=address_pair_query.reg_key).first()

    # Delete AddressPair
    ip_address_query = IpAddress.query.filter_by(address_v4=ip_address).first()
    mac_address_query = MacAddress.query.filter_by(address=mac_address).first()
    address_pair = AddressPair.query.filter_by(mac_address=mac_address_query.id, ip_address=ip_address_query.id).first()
    db.session.delete(address_pair)

    # Disable Shaping
    if reg_key_query.id in accounting_srv.shaped_reg_keys:
        shaping_manager.disable_shaping_for_ip(ip_address_query.id, ip_address_query.address_v4)

    # Delete IP Address
    ip_address_query = IpAddress.query.filter_by(address_v4=ip_address).first()
    db.session.delete(ip_address_query)

    # Delete MAC Address
    mac_address_query = MacAddress.query.filter_by(address=mac_address).first()
    db.session.delete(mac_address_query)

    db.session.commit()

    # Disable Accounting
    if AddressPair.query.filter_by(reg_key=reg_key_query.id).count() == 0:
        iptables_accounting_manager.remove_ip_from_box(reg_key_query.id, ip_address)
        iptables_accounting_manager.remove_accounter_chain(reg_key_query.id)
    else:
        iptables_accounting_manager.remove_ip_from_box(reg_key_query.id, ip_address)

    # Spoofing Protection
    arp_manager.remove_static_arp_entry(ip_address)

    # Setup dnsmasq
    dnsmasq_manager.remove_static_lease(mac_address, ip_address)
    dnsmasq_srv.reload()

    # Setup Firewall
    iptables_rules_manager.relock_registered_device(ip_address)

def delete_registration_key(reg_key_query):
    try:
        address_pair_query = AddressPair.query.filter_by(reg_key=reg_key_query.id).all()
        for row in address_pair_query:
            ip_address_query = IpAddress.query.filter_by(id=row.ip_address).first()
            deregister_device(ip_address_query.address_v4)

        traffic_query = Traffic.query.filter_by(reg_key=reg_key_query.id).all()
        for row in traffic_query:
            db.session.delete(row)

        identity_query = Identity.query.filter_by(id=reg_key_query.identity).first()
        db.session.delete(reg_key_query)
        db.session.commit()
        db.session.delete(identity_query)

        db.session.commit()
        return True
    except:
        return False

class RegistrationError(Exception):
    pass

