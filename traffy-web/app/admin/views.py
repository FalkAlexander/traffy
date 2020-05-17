from flask import Flask, render_template, request, jsonify, flash, session, redirect, url_for
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_user, login_required, logout_user
from dateutil import rrule
from datetime import datetime, timedelta
from user_agents import parse
from flask_weasyprint import HTML, render_pdf
from . import admin, supervisor_functions
from .. import db, server, login_manager
from ..models import SupervisorAccount, Role
import config
import time


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
    legend_downlink = _l("Downlink") + " (GiB)"
    legend_uplink = _l("Uplink") + " (GiB)"

    values_downlink, values_uplink, labels, active_users, registered_users, average_credit, shaped_users = server.get_supervisor_dashboard_stats()

    return render_template("/admin/dashboard.html",
                           labels=labels,
                           values_downlink=values_downlink,
                           values_uplink=values_uplink,
                           legend_downlink=legend_downlink,
                           legend_uplink=legend_uplink,
                           active_users=active_users,
                           registered_users=registered_users,
                           average_credit=average_credit,
                           shaped_users=shaped_users)

@admin.route("/admin/regcodes", methods=["GET", "POST"])
@login_required
def reg_codes():
    date = datetime.today().date()

    if "search_box" in request.form:
        search_term = request.form["search_box"].lower()
        search_results = server.get_reg_codes_search_results(search_term)

        return render_template("/admin/regcodes.html", rows=search_results, clear_button=True)

    rows = server.construct_reg_code_list()

    if "clear_btn" in request.form:
        return render_template("/admin/regcodes.html", rows=rows, dev_mode=config.DEV_MODE)

    if "add_key_btn" in request.form:
        return redirect("/admin/add-regcode")

    if "add_test_btn" in request.form:
        server.create_reg_key_test()
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
            room = request.form["room"]
            if first_name == "" or surname == "" or mail == "" or room == "":
                flash(_l("Please fill out all input forms."))
                return render_template("/admin/add-regcode.html")
            else:
                reg_key = server.add_registration_code(first_name, surname, mail, room)
                return redirect("/admin/regcodes/" + reg_key)

    return render_template("/admin/add-regcode.html")

@admin.route("/admin/regcodes/<reg_key>/delete/<ip_address>", methods=["GET", "POST"])
@login_required
def delete_device(reg_key, ip_address):
    if not current_user.is_admin() and not current_user.is_helpdesk():
        return redirect("/admin/dashboard")

    server.deregister_device(ip_address)
    flash(_l("Device unregistered"))
    return redirect("/admin/regcodes/" + reg_key)

@admin.route("/admin/regcodes/<reg_key>", methods=["GET", "POST"])
@login_required
def reg_code(reg_key):
    if server.reg_key_exists(reg_key) is False:
        flash(_l("Invalid registration key."))
        return redirect("/admin/regcodes")

    # User Settings Post Processing
    if request.method == "POST":
        # Dev Mode
        if "fake_device_btn" in request.form:
            server.register_device_test(reg_key, request.headers.get("User-Agent"))
            return redirect("/admin/regcodes/" + reg_key)

        # Instruction Download
        if "download_btn" in request.form:
            max_saved_volume, initial_volume, daily_topup_volume, shaping_speed, traffy_ip, traffy_domain, max_devices = server.get_instruction_pdf_values()
            first_name, last_name, room = server.get_reg_code_identity(reg_key)
            creation_date = str(int(time.time()))
            current_supervisor = current_user.get_last_name() + ", " + current_user.get_first_name() + " (" + current_user.get_role() + ")"

            html = render_template("/admin/pdf/instruction.html",
                                   reg_key=reg_key,
                                   initial_volume=initial_volume,
                                   daily_topup_volume=daily_topup_volume,
                                   max_saved_volume=max_saved_volume,
                                   shaping_speed=shaping_speed,
                                   traffy_ip=traffy_ip,
                                   traffy_domain=traffy_domain,
                                   max_devices=max_devices,
                                   first_name=first_name,
                                   last_name=last_name,
                                   room=room,
                                   creation_date=creation_date,
                                   current_user=current_user)

            return render_pdf(HTML(string=html), download_filename=last_name.encode("ascii", errors="xmlcharrefreplace").decode() + "," + first_name.encode("ascii", errors="xmlcharrefreplace").decode() + "_Instruction.pdf")

        # Set Custom Credit
        if "custom_credit_enable" in request.form:
            valid = server.set_reg_key_custom_credit(reg_key, request.form["custom_credit_input"])

            if not valid:
                flash(_l("Input entered is invalid."))

            return redirect("/admin/regcodes/" + reg_key)

        # Set Custom Top-Up
        if "custom_topup_enable" in request.form:
            valid = server.set_reg_key_custom_topup(reg_key, request.form["custom_topup_input"])

            if not valid:
                flash(_l("Input entered is invalid."))

            return redirect("/admin/regcodes/" + reg_key)

        # Disable Custom Top-Up
        if "custom_topup_disable" in request.form:
            success = server.set_reg_key_disable_custom_topup(reg_key)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key)

        # Set Custom Maximum Credit
        if "custom_max_enable" in request.form:
            valid = server.set_reg_key_custom_max_enable(reg_key, request.form["custom_max_input"])

            if not valid:
                flash(_l("Input entered is invalid."))

            return redirect("/admin/regcodes/" + reg_key)

        # Disable Custom Maximum Credit
        if "custom_max_disable" in request.form:
            success = server.set_reg_key_custom_max_disable(reg_key)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key)
        
        # Change User Room
        if "change_room_number" in request.form:
            success = server.set_reg_key_room_number(reg_key, request.form["change_room_number"], request.form["change_room_number_date"])

            if not success:
                flash(_l("An error occured."))
            
            return redirect("/admin/regcodes/" + reg_key)

        # Enable Accounting
        if "enable_accounting" in request.form:
            success = server.set_reg_key_enable_accounting(reg_key)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key)

        # Disable Accounting
        if "disable_accounting" in request.form:
            success = server.set_reg_key_disable_accounting(reg_key)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key)

        # Activate Registration Key
        if "activate_code" in request.form:
            success = server.set_reg_key_activated(reg_key)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key)

        # Deactivate Registration Key
        if "deactivate_code" in request.form:
            success = server.set_reg_key_deactivated(reg_key)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key)

        # Delete Registration Code
        if "delete_code" in request.form:
            success = server.delete_registration_key(reg_key, request.form["delete_code_date"])

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes")


    # Statistics
    legend_downlink = _l("Downlink") + " (GiB)"
    legend_downlink_shaped = _l("Shaped Downlink") + " (GiB)"
    legend_uplink = _l("Uplink") + " (GiB)"
    legend_uplink_shaped = _l("Shaped Uplink") + " (GiB)"
    stat_volume_left, stat_created_on, stat_shaped, stat_status, labels, values_downlink, values_downlink_shaped, values_uplink, values_uplink_shaped = server.get_reg_code_statistics(reg_key)

    if stat_shaped:
        stat_shaped = _l("Yes")
    else:
        stat_shaped = _l("No")

    if stat_status:
        stat_status = _l("Enabled")
    else:
        stat_status = _l("Disabled")

    # Devices
    device_list = server.get_reg_code_device_list(reg_key)

    # User Settings Variables
    custom_volume_enabled, value_custom_topup, custom_max_enabled, value_max_volume, accounting_enabled, key_active = server.get_reg_code_settings_values(reg_key)

    # Room
    room = server.get_reg_code_room(reg_key)

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
                           key_active=key_active,
                           room=room)

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

@admin.route("/admin/infrastructure", methods=["GET", "POST"])
@login_required
def infrastructure():
    date = datetime.today().date()

    if "search_box" in request.form:
        search_term = request.form["search_box"].lower()
        search_results = server.get_reg_codes_search_results(search_term)

        return render_template("/admin/infrastructure.html", rows=search_results, clear_button=True)

    rows = server.construct_reg_code_list()

    if "clear_btn" in request.form:
        return render_template("/admin/infrastructure.html", rows=rows, dev_mode=config.DEV_MODE)

    if "add_key_btn" in request.form:
        return redirect("/admin/add-regcode")

    if "add_test_btn" in request.form:
        server.create_reg_key_test()
        return redirect("/admin/infrastructure")

    return render_template("/admin/infrastructure.html", rows=rows, dev_mode=config.DEV_MODE)

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

