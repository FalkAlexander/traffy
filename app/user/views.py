from flask import Flask, render_template, request, jsonify, flash, session, redirect, url_for
from flask_babel import lazy_gettext as _l
from . import user, user_functions
from .. import db, babel, dnsmasq_srv, accounting_srv
from ..models import RegistrationKey, IpAddress, MacAddress, AddressPair
from ..util import lease_parser, dnsmasq_manager, iptables_rules_manager, iptables_accounting_manager, shaping_manager, arp_manager
import datetime
import config


@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(config.LANGUAGES)

@user.route("/", methods=["GET"])
def index():
    init_session_variables()

    registration = is_registered()
    if registration is True:
        return redirect("/dashboard", code=307)
    elif registration == "stolen":
        return render_template("errors/ip_stolen.html")
    elif registration == "deactivated":
        return render_template("errors/deactivated.html")
    else:
        return redirect("/register", code=307)

@user.route("/register", methods=["GET", "POST"])
def register():
    init_session_variables()

    registration = is_registered()
    if registration is True:
        return redirect("/dashboard", code=307)
    elif registration == "stolen":
        return render_template("errors/ip_stolen.html")
    elif registration == "deactivated":
        return render_template("errors/deactivated.html")

    if request.method == "POST":
        if "register_btn" in request.form:
            input_key = request.form["key"].lower()

            reg_key_query = RegistrationKey.query.filter_by(key=input_key).first()
            if input_key == "" or reg_key_query is None:
                flash(_l("Invalid registration key.") + " Code: 100")
                return render_template("user/register.html")

            reg_key_query = RegistrationKey.query.filter_by(key=input_key).first()
            address_pair_count_query = AddressPair.query.filter_by(reg_key=reg_key_query.id).count()
            if address_pair_count_query >= config.MAX_MAC_ADDRESSES_PER_REG_KEY:
                flash(_l("Maximum number of devices already registered.") + " Code: 110")
                return render_template("user/register.html")

            session["input_key"] = input_key
            return redirect("/conditions", code=307)

    return render_template("user/register.html")

@user.route("/conditions", methods=["POST"])
def conditions():
    registration = is_registered()
    if registration is True:
        return redirect("/dashboard", code=307)
    elif registration == "stolen":
        return render_template("errors/ip_stolen.html")
    elif registration == "deactivated":
        return render_template("errors/deactivated.html")

    input_key = session.get("input_key")
    ip_address = session.get("ip_address")

    reg_key_query = RegistrationKey.query.filter_by(key=input_key).first()
    if input_key == "" or reg_key_query is None:
        flash(_l("Invalid registration key.") + " Code: 100")
        return render_template("user/register.html")

    if "accept_btn" in request.form:
        try:
            user_functions.register_device(input_key, ip_address, request)
        except RegistrationError as ex:
            return render_template("user/register.html")
        
        return redirect("/dashboard", code=307)

    return render_template("user/conditions.html")

@user.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    registration = is_registered()
    if registration is False:
        return redirect("/register", code=307)
    elif registration == "stolen":
        return render_template("errors/ip_stolen.html")
    elif registration == "deactivated":
        return render_template("errors/deactivated.html")

    init_session_variables()
    ip_address = session.get("ip_address")

    ip_address_query = IpAddress.query.filter_by(address_v4=ip_address).first()
    address_pair_query = AddressPair.query.filter_by(ip_address=ip_address_query.id).first()
    reg_key_query = RegistrationKey.query.filter_by(id=address_pair_query.reg_key).first()
    volume_left, credit = accounting_srv.get_credit(reg_key_query, gib=True)
    if volume_left < 0:
        volume_left = 0

    mac_address_query = MacAddress.query.filter_by(id=address_pair_query.mac_address).first()
    user_agent_string = request.headers.get("User-Agent")
    if mac_address_query.user_agent != user_agent_string and not len(user_agent_string) > 500:
        mac_address_query.user_agent = request.headers.get("User-Agent")
        db.session.commit()

    if "reedem_dashboard_btn" in request.form:
        return redirect("/reedem", code=307)

    if "deregister_dashboard_btn" in request.form:
        return redirect("/deregister", code=307)

    return render_template("user/dashboard.html", volume_left=volume_left, credit=credit)

@user.route("/reedem", methods=["POST"])
def reedem():
    registration = is_registered()
    if registration is False:
        return redirect("/register", code=307)
    elif registration == "stolen":
        return render_template("errors/ip_stolen.html")
    elif registration == "deactivated":
        return render_template("errors/deactivated.html")

    if "reedem_btn" in request.form:
        raw_voucher = request.form["voucher"]
        voucher = raw_voucher.lower()
        if voucher == "":
            flash(_l("Invalid voucher"))
            return render_template("user/reedem.html")
        else:
            return redirect("/dashboard", code=307)

    return render_template("user/reedem.html")
    
@user.route("/deregister", methods=["POST"])
def deregister():
    registration = is_registered()
    if registration is False:
        return redirect("/register", code=307)
    elif registration == "stolen":
        return render_template("errors/ip_stolen.html")
    elif registration == "deactivated":
        return render_template("errors/deactivated.html")

    if "deregister_btn" in request.form:
        ip_address = session.get("ip_address")
        user_functions.deregister_device(ip_address)

        return redirect("/register", code=307)

    return render_template("user/deregister.html")

@user.route("/about", methods=["GET", "POST"])
def about():
    return render_template("user/about.html")

def init_session_variables():
    session["ip_address"] = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

def is_registered():
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)
    mac_address = lease_parser.get_mac_from_ip(ip_address)
    
    ip_address_query = IpAddress.query.filter_by(address_v4=ip_address).first()
    mac_address_query = MacAddress.query.filter_by(address=mac_address).first()
    
    if ip_address_query is None and mac_address_query is None:
        return False
    
    # If someone with a faulty static ip NIC configuration has stolen an users ip
    if ip_address_query is None and mac_address_query is not None:
        return "stolen"

    address_pair_query = AddressPair.query.filter_by(mac_address=mac_address_query.id, ip_address=ip_address_query.id).first()
    if address_pair_query is None:
        return False
    else:
        reg_key_query = RegistrationKey.query.filter_by(id=address_pair_query.reg_key).first()
        if reg_key_query.active is False:
            return "deactivated"
        else:
            return True

