from flask import Flask, render_template, request, jsonify, flash, session, redirect, url_for
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_user, login_required, logout_user
from . import admin, supervisor_functions
from ..user import user_functions
from .. import db, babel, dnsmasq_srv, accounting_srv, login_manager, dev_mode_test
from ..models import RegistrationKey, IpAddress, MacAddress, Identity, Traffic, AddressPair, SupervisorAccount, Role
from ..util import lease_parser, dnsmasq_manager, iptables_rules_manager, iptables_accounting_manager, generate_registration_key
from dateutil import rrule
from datetime import datetime, timedelta
from user_agents import parse
from flask_weasyprint import HTML, render_pdf
import config

@admin.route("/admin", methods=["GET"])
def index():
    return redirect("/admin/login")

@admin.route("/admin/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect("/admin/dashboard")

    if "login_btn" in request.form and request.method == "POST":
        input_username = request.form["username"]
        input_password = request.form["password"]

        user = SupervisorAccount.query.filter_by(username=input_username).first()
        if user is not None:
            if user.check_password(input_password) is True:
                login_user(user)
                next = request.args.get("next")
                return redirect(next or "/admin/dashboard")

        flash(_l("Wrong credentials. This attempt got reported."))

    return render_template("/admin/login.html")

@admin.route("/admin/dashboard", methods=["GET", "POST"])
@login_required
def dashboard():
    today = datetime.today().date()
    passed_days = today - timedelta(days=10)

    legend_downlink = _l("Downlink") + " (GiB)"
    legend_uplink = _l("Uplink") + " (GiB)"
    values_downlink = []
    values_uplink = []
    labels = []

    for date in rrule.rrule(rrule.DAILY, dtstart=passed_days, until=today):
        traffic_query = Traffic.query.filter_by(timestamp=date).all()
        downlink = 0
        uplink = 0
        if traffic_query is not None:
            for row in traffic_query:
                downlink += __to_gib(row.ingress)
                uplink += __to_gib(row.egress)

        values_downlink.append(downlink)
        values_uplink.append(uplink)
        labels.append(date.strftime("%d.%m."))

    active_users = RegistrationKey.query.filter_by(active=True).count()
    ip_adresses = IpAddress.query.count()
    ratio = "N/A"
    if ip_adresses != 0:
        ratio = round(active_users / IpAddress.query.count(), 1)

    traffic_rows = Traffic.query.filter_by(timestamp=today).all()

    average_credit = 0
    count = 0
    for row in traffic_rows:
        count += 1
        average_credit += (row.credit - (row.ingress + row.egress)) / 1073741824

    if count != 0:
        average_credit = round(average_credit, 3)
    else:
        average_credit = 0

    shaped_users = len(accounting_srv.shaped_reg_keys)

    return render_template("/admin/dashboard.html",
                           labels=labels,
                           values_downlink=values_downlink,
                           values_uplink=values_uplink,
                           legend_downlink=legend_downlink,
                           legend_uplink=legend_uplink,
                           active_users=active_users,
                           ratio=ratio,
                           average_credit=average_credit,
                           shaped_users=shaped_users)

@admin.route("/admin/regcodes", methods=["GET", "POST"])
@login_required
def reg_codes():
    rows = []
    date = datetime.today().date()

    if "search_box" in request.form:
        search_term = request.form["search_box"].lower()
        search_results = []

        reg_key_query = []
        for query in db.session.query(RegistrationKey).all():
            if search_term in query.key:
                reg_key_query.append(query)
            else:
                identity = Identity.query.filter_by(id=query.identity).first()

                if search_term in identity.first_name.lower() or search_term in identity.last_name.lower() or search_term in identity.mail.lower():
                    reg_key_query.append(query)

        reg_key_query.reverse()

        for row in reg_key_query:
            identity = Identity.query.filter_by(id=row.identity).first()
            credit = accounting_srv.get_credit(row, gib=True)[0]
            if credit < 0:
                credit = 0
            search_results.append(KeyRow(row.key, identity.last_name, identity.first_name, credit, row.active))

        return render_template("/admin/regcodes.html", rows=search_results, clear_button=True)

    for row in RegistrationKey.query.all():
        identity = Identity.query.filter_by(id=row.identity).first()
        credit = accounting_srv.get_credit(row, gib=True)[0]
        if credit < 0:
            credit = 0
        rows.append(KeyRow(row.key, identity.last_name, identity.first_name, credit, row.active))

    rows.reverse()

    if "clear_btn" in request.form:
        return render_template("/admin/regcodes.html", rows=rows, dev_mode=config.DEV_MODE)

    if "add_key_btn" in request.form:
        return redirect("/admin/add-regcode")

    if "add_test_btn" in request.form:
        dev_mode_test.add_reg_key()
        return redirect("/admin/regcodes")

    return render_template("/admin/regcodes.html", rows=rows, dev_mode=config.DEV_MODE)

@admin.route("/admin/add-regcode", methods=["GET", "POST"])
@login_required
def add_regcode():
    if request.method == "POST":
        if "cancel_btn" in request.form:
            return redirect("/admin/regcodes")

        if "add_key_btn" in request.form:
            first_name = request.form["first_name"]
            surname = request.form["surname"]
            mail = request.form["mail"]
            if first_name == "" or surname == "" or mail == "":
                flash(_l("Please fill out all input forms."))
                return render_template("/admin/add-regcode.html")
            else:
                db.session.add(Identity(first_name=first_name, last_name=surname, mail=mail))
                identity = Identity.query.filter_by(first_name=first_name, last_name=surname, mail=mail).first()

                reg_key = generate_registration_key.generate()

                db.session.add(RegistrationKey(key=reg_key, identity=identity.id))
                reg_key_query = RegistrationKey.query.filter_by(key=reg_key).first()

                db.session.add(Traffic(reg_key=reg_key_query.id, timestamp=datetime.today().date(), credit=config.DAILY_TOPUP_VOLUME, ingress=0, egress=0, ingress_shaped=0, egress_shaped=0))

                db.session.commit()
                return redirect("/admin/regcodes/" + reg_key)

    return render_template("/admin/add-regcode.html")

@admin.route("/admin/regcodes/<reg_key>/delete/<ip_address>", methods=["GET", "POST"])
@login_required
def delete_device(reg_key, ip_address):
    if not current_user.is_admin() and not current_user.is_helpdesk():
        return redirect("/admin/dashboard")

    user_functions.deregister_device(ip_address)
    flash(_l("Device unregistered"))
    return redirect("/admin/regcodes/" + reg_key)

@admin.route("/admin/regcodes/<reg_key>", methods=["GET", "POST"])
@login_required
def reg_code(reg_key):
    reg_key_query = RegistrationKey.query.filter_by(key=reg_key).first()
    if reg_key_query is None:
        flash(_l("Invalid registration key."))
        return redirect("/admin/regcodes")

    # User Settings Post Processing
    if request.method == "POST":
        # Dev Mode
        if "fake_device_btn" in request.form:
            dev_mode_test.register_device(reg_key_query, request)
            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Instruction Download
        if "download_btn" in request.form:
            return render_pdf(url_for("admin.create_instruction_pdf", reg_key=reg_key_query.key))

        # Set Custom Credit
        if "custom_credit_enable" in request.form:
            valid = accounting_srv.set_custom_credit(reg_key_query,
                                                     request.form["custom_credit_input"])

            if not valid:
                flash(_l("Input entered is invalid."))

            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Set Custom Top-Up
        if "custom_topup_enable" in request.form:
            valid = accounting_srv.set_custom_topup(reg_key_query,
                                                     request.form["custom_topup_input"])

            if not valid:
                flash(_l("Input entered is invalid."))

            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Disable Custom Top-Up
        if "custom_topup_disable" in request.form:
            success = accounting_srv.disable_custom_topup(reg_key_query)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Set Custom Maximum Credit
        if "custom_max_enable" in request.form:
            valid = accounting_srv.set_custom_max_volume(reg_key_query,
                                                     request.form["custom_max_input"])

            if not valid:
                flash(_l("Input entered is invalid."))

            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Disable Custom Maximum Credit
        if "custom_max_disable" in request.form:
            success = accounting_srv.disable_custom_max_volume(reg_key_query)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Enable Accounting
        if "enable_accounting" in request.form:
            success = accounting_srv.enable_accounting_for_reg_key(reg_key_query)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Disable Accounting
        if "disable_accounting" in request.form:
            success = accounting_srv.disable_accounting_for_reg_key(reg_key_query)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Activate Registration Key
        if "activate_code" in request.form:
            success = accounting_srv.activate_registration_key(reg_key_query)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Deactivate Registration Key
        if "deactivate_code" in request.form:
            success = accounting_srv.deactivate_registration_key(reg_key_query)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key_query.key)

        # Delete Registration Code
        if "delete_code" in request.form:
            success = user_functions.delete_registration_key(reg_key_query)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes")


    # Statistics
    traffic_query = Traffic.query.filter_by(reg_key=reg_key_query.id).first()
    stat_volume_left = accounting_srv.get_credit(reg_key_query, gib=True)[0]
    stat_created_on = accounting_srv.get_reg_key_creation_timestamp(reg_key_query, "%d.%m.%Y")
    stat_shaped = accounting_srv.get_count_shaped_reg_keys(reg_key_query)
    stat_status = accounting_srv.is_registration_key_active(reg_key_query)

    if stat_volume_left < 0:
        stat_volume_left = 0

    if stat_shaped:
        stat_shaped = _l("Yes")
    else:
        stat_shaped = _l("No")

    if stat_status:
        stat_status = _l("Enabled")
    else:
        stat_status = _l("Disabled")

    legend_downlink = _l("Downlink") + " (GiB)"
    legend_downlink_shaped = _l("Shaped Downlink") + " (GiB)"
    legend_uplink = _l("Uplink") + " (GiB)"
    legend_uplink_shaped = _l("Shaped Uplink") + " (GiB)"
    values_downlink = []
    values_downlink_shaped = []
    values_uplink = []
    values_uplink_shaped = []
    labels = []

    today = datetime.today().date()
    passed_days = today - timedelta(days=10)

    for date in rrule.rrule(rrule.DAILY, dtstart=passed_days, until=today):
        traffic_query = Traffic.query.filter_by(reg_key=reg_key_query.id, timestamp=date).all()
        downlink = 0
        downlink_shaped = 0
        uplink = 0
        uplink_shaped = 0

        if traffic_query is not None:
            for row in traffic_query:
                downlink += __to_gib(row.ingress)
                downlink_shaped += __to_gib(row.ingress_shaped)
                uplink += __to_gib(row.egress)
                uplink_shaped += __to_gib(row.egress_shaped)

        values_downlink.append(downlink)
        values_downlink_shaped.append(downlink_shaped)
        values_uplink.append(uplink)
        values_uplink_shaped.append(uplink_shaped)
        labels.append(date.strftime("%d.%m."))

    # Devices
    device_list = []
    for row in AddressPair.query.filter_by(reg_key=reg_key_query.id).all():
        ip_address_query = IpAddress.query.filter_by(id=row.ip_address).first()
        mac_address_query = MacAddress.query.filter_by(id=row.mac_address).first()

        device_list.append(DeviceRow(ip_address_query.address_v4, mac_address_query.address, mac_address_query.user_agent, mac_address_query.first_known_since))

    device_list.reverse()

    # User Settings Variables
    # Custom Top-Up
    custom_volume_enabled = False
    value_custom_topup = 0
    if reg_key_query.daily_topup_volume is not None:
        custom_volume_enabled = True
        value_custom_topup = __to_gib(reg_key_query.daily_topup_volume)
    # Custom Max Value
    custom_max_enabled = False
    value_max_volume = 0
    if reg_key_query.max_volume is not None:
        custom_max_enabled = True
        value_max_volume = __to_gib(reg_key_query.max_volume)
    # Disable Accounting
    accounting_enabled = reg_key_query.enable_accounting
    # Deactivate Registration Key
    key_active = reg_key_query.active

    return render_template("/admin/key-page.html",
                           dev_mode=config.DEV_MODE,
                           reg_key=reg_key,
                           stat_volume_left=stat_volume_left,
                           stat_created_on=stat_created_on,
                           stat_shaped=stat_shaped,
                           stat_status=stat_status,
                           labels=labels,
                           values_downlink=values_downlink,
                           values_downlink_shaped=values_downlink_shaped,
                           values_uplink=values_uplink,
                           values_uplink_shaped=values_uplink_shaped,
                           legend_downlink=legend_downlink,
                           legend_downlink_shaped=legend_downlink_shaped,
                           legend_uplink=legend_uplink,
                           legend_uplink_shaped=legend_uplink_shaped,
                           device_list=device_list,
                           custom_volume_enabled=custom_volume_enabled,
                           value_custom_topup=value_custom_topup,
                           custom_max_enabled=custom_max_enabled,
                           value_max_volume=value_max_volume,
                           accounting_enabled=accounting_enabled,
                           key_active=key_active)

@admin.route("/admin/accounts", methods=["GET", "POST"])
@login_required
def accounts():
    if not current_user.is_admin():
        return redirect("/admin/dashboard")

    rows = []
    for row in SupervisorAccount.query.all():
        role = Role.query.filter_by(id=row.role).first()
        rows.append(AccountRow(row.username, row.last_name, row.first_name, role.role))

    if request.method == "POST":
        if "add_account_btn" in request.form:
            return redirect("/admin/add-account")

    return render_template("/admin/accounts.html", rows=rows)

@admin.route("/admin/accounts/<username>", methods=["GET", "POST"])
@login_required
def user(username):
    if not current_user.is_admin():
        return redirect("/admin/dashboard")

    account_query = SupervisorAccount.query.filter_by(username=username).first()
    if account_query is None:
        flash(_l("Invalid supervisor account."))
        return redirect("/admin/accounts")

    # Account Settings Post Processing
    if request.method == "POST":
        # Change notifications behaviour
        if "change_notifications_btn" in request.form:
            valid = supervisor_functions.set_account_notifications(account_query,
                                                                    request.form.get("checkbox_shaped"),
                                                                    request.form.get("checkbox_failures"),
                                                                    request.form.get("checkbox_critical"))
            if not valid:
                flash(_l("An error occured."), "error")

            return redirect("/admin/accounts/" + account_query.username)

        # Change password
        if "change_password_btn" in request.form:
            valid = supervisor_functions.set_account_password(account_query,
                                                                request.form["password_input"])
            if not valid:
                flash(_l("Password requirements not met."), "error")
            else:
                flash(_l("Password changed."), "success")

            return redirect("/admin/accounts/" + account_query.username)

        # Change email
        if "change_mail_btn" in request.form:
            valid = supervisor_functions.set_account_mail(account_query,
                                                            request.form["mail_input"])
            if not valid:
                flash(_l("Mail address entered is invalid."), "error")
            else:
                flash(_l("Mail address changed."), "success")

            return redirect("/admin/accounts/" + account_query.username)

        # Delete account
        if "delete_account_btn" in request.form:
            if SupervisorAccount.query.count() == 1:
                flash(_l("No other supervisor account left, cannot delete this one."), "error")
                return redirect("/admin/accounts/" + account_query.username)

            valid = supervisor_functions.delete_account(account_query)
            if not valid:
                flash(_l("Error deleting account."), "error")
                return redirect("/admin/accounts/" + account_query.username)
            else:
                flash(_l("Account deleted."))
                return redirect("/admin/login")

    return render_template("/admin/account-page.html",
                           username=username,
                           notify_shaped=account_query.notify_shaping,
                           notify_failures=account_query.notify_login_attempts,
                           notify_critical=account_query.notify_critical_events,
                           mail_address=account_query.mail
                           )

@admin.route("/admin/add-account", methods=["GET", "POST"])
@login_required
def add_account():
    if not current_user.is_admin():
        return redirect("/admin/dashboard")

    roles = []
    for role in Role.query.all():
        roles.append(role.role)

    if request.method == "POST":
        if "cancel_btn" in request.form:
            return redirect("/admin/accounts")

        if "add_key_btn" in request.form:
            username = request.form["username"]
            first_name = request.form["first_name"]
            surname = request.form["surname"]
            mail = request.form["mail"]
            password = request.form["password"]
            role = request.form["role"]

            if username == "" or first_name == "" or surname == "" or mail == "" or password == "" or role == "":
                flash(_l("Please fill out all input forms."))
                return render_template("/admin/add-account.html", roles=roles)
            else:
                valid = supervisor_functions.create_account(username, first_name, surname, mail, password, role)
                if not valid:
                    flash(_l("Account could not get created."))
                    return render_template("/admin/add-account.html", roles=roles)

                return redirect("/admin/accounts/" + username)

    return render_template("/admin/add-account.html", roles=roles)

@admin.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect("/admin/login")

@login_manager.user_loader
def load_user(user_id):
    if user_id is not None:
        return SupervisorAccount.query.get(user_id)
    else:
        return None

@login_manager.unauthorized_handler
def unauthorized():
    flash(_l("Login to access that resource."))
    return redirect("/admin/login")

@admin.route("/admin/regcodes/render-instruction-pdf/<reg_key>", methods=["GET"])
def create_instruction_pdf(reg_key):
    reg_key_query = RegistrationKey.query.filter_by(key=reg_key).first()

    if reg_key_query is None:
        flash(_l("Invalid registration key."))
        return redirect("/admin/regcodes")

    max_saved_volume = __to_gib(accounting_srv.get_max_saved_volume(), decimals=0)
    daily_topup_volume = __to_gib(accounting_srv.get_daily_topup_volume(), decimals=0)

    return render_template("/admin/pdf/instruction.html",
                           reg_key=reg_key,
                           daily_topup_volume=daily_topup_volume,
                           max_saved_volume=max_saved_volume,
                           shaping_speed=config.SHAPING_SPEED,
                           traffy_url=config.THIS_SERVER_IP_WAN,
                           max_devices=config.MAX_MAC_ADDRESSES_PER_REG_KEY,
                           admin_name=config.ADMIN_NAME,
                           admin_mail=config.ADMIN_MAIL,
                           admin_room=config.ADMIN_ROOM)

class KeyRow():
    reg_key = ""
    last_name = ""
    first_name = ""
    credit = ""
    active = True

    def __init__(self, reg_key, last_name, first_name, credit, active):
        self.reg_key = reg_key
        self.last_name = last_name
        self.first_name = first_name
        self.credit = credit
        self.active = active

class DeviceRow():
    ip_address = ""
    mac_address = ""
    type = ""
    registered_since = ""

    def __init__(self, ip_address, mac_address, user_agent, registered_since):
        self.ip_address = ip_address
        self.mac_address = mac_address
        self.type = self.find_device(user_agent)
        self.registered_since = registered_since.strftime("%d.%m.%Y %H:%M:%S")

    def find_device(self, user_agent):
        device_string = ""
        user_agent = parse(user_agent)

        if user_agent.is_mobile:
            if user_agent.is_touch_capable:
                device_string += "Smartphone / "
                device_string += user_agent.device.brand + " / " + user_agent.device.family + " / "
            else:
                device_string += "Handy / "
                device_string += user_agent.device.brand + " / " + user_agent.device.family + " / "
        elif user_agent.is_tablet:
            device_string += "Tablet / "
        elif user_agent.is_pc:
            device_string += "Desktop / "

        device_string += user_agent.os.family + " " + user_agent.os.version_string

        if device_string == "Other":
            device_string = _l("Unknown")

        return device_string

class AccountRow():
    username = ""
    last_name = ""
    first_name = ""
    role = ""

    def __init__(self, username, last_name, first_name, role):
        self.username = username
        self.last_name = last_name
        self.first_name = first_name
        self.role = role

#
# Private
#

def __to_gib(bytes, decimals=3):
    return round(bytes / 1073741824, decimals)

def __to_bytes(gib):
    return int(gib * 1073741824)

