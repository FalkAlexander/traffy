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


