import config
import subprocess
import threading
import util


def response_check(ip_address, mac_address):
    if util.arping(ip_address) is False:
        return
    
    util.release(ip_address, mac_address)
    print("Released " + ip_address + " / " + mac_address)

leases = util.get_leases()

for lease in leases:
    ip_address = lease[1]
    mac_address = lease[0]

    resp_thread = threading.Thread(target=response_check, args=(ip_address, mac_address))
    resp_thread.start()
