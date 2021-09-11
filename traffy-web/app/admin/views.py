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

from flask import Flask, render_template, request, jsonify, flash, session, redirect, url_for, send_file
from flask_babel import lazy_gettext as _l
from flask_login import current_user, login_user, login_required, logout_user
from dateutil import rrule
from datetime import datetime, timedelta
from user_agents import parse
from flask_weasyprint import HTML, render_pdf
from . import admin, supervisor_functions, notification_functions
from .. import db, server, login_manager
from ..models import SupervisorAccount, Role, Notification
import config
import math
import time
import zipfile


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
    legend_downlink = "↓ " + _l("Accounted")
    legend_downlink_unlimited_range = "↓ " + _l("Timerule")
    legend_downlink_shaped = "↓ " + _l("Shaped")
    legend_downlink_excepted = "↓ " + _l("Exceptions")
    legend_uplink = "↑ " + _l("Accounted")
    legend_uplink_unlimited_range = "↑ " + _l("Timerule")
    legend_uplink_shaped = "↑ " + _l("Shaped")
    legend_uplink_excepted = "↑ " + _l("Exceptions")

    values_downlink, values_downlink_unlimited_range, values_downlink_shaped, values_downlink_excepted, values_uplink, values_uplink_unlimited_range, values_uplink_shaped, values_uplink_excepted, labels, active_users, registered_users, average_credit, shaped_users = server.get_supervisor_dashboard_stats()

    show_erp = server.is_erp_integration_enabled()

    master_data_updates_available = server.is_master_updates_available()

    return render_template("/admin/dashboard.html",
                           labels=labels,
                           values_downlink=values_downlink,
                           values_downlink_unlimited_range=values_downlink_unlimited_range,
                           values_downlink_shaped=values_downlink_shaped,
                           values_downlink_excepted=values_downlink_excepted,
                           values_uplink=values_uplink,
                           values_uplink_unlimited_range=values_uplink_unlimited_range,
                           values_uplink_shaped=values_uplink_shaped,
                           values_uplink_excepted=values_uplink_excepted,
                           legend_downlink=legend_downlink,
                           legend_downlink_unlimited_range=legend_downlink_unlimited_range,
                           legend_downlink_shaped=legend_downlink_shaped,
                           legend_downlink_excepted=legend_downlink_excepted,
                           legend_uplink=legend_uplink,
                           legend_uplink_unlimited_range=legend_uplink_unlimited_range,
                           legend_uplink_shaped=legend_uplink_shaped,
                           legend_uplink_excepted=legend_uplink_excepted,
                           active_users=active_users,
                           registered_users=registered_users,
                           average_credit=average_credit,
                           shaped_users=shaped_users,
                           show_erp=show_erp,
                           master_data_updates_available=master_data_updates_available)

@admin.route("/admin/master-updates", methods=["GET", "POST"])
@login_required
def master_updates():
    identities_creatable = server.get_identity_master_data_updates_createable()
    identities_updateable = server.get_identity_master_data_updates_updateable()
    identities_deletable = server.get_identity_master_data_updates_deletables()
    return render_template("/admin/master-updates.html",
                           identities_creatable=identities_creatable,
                           identities_updateable=identities_updateable,
                           identities_deletable=identities_deletable)

@admin.route("/admin/regcodes", methods=["GET", "POST"])
@login_required
def reg_codes():
    date = datetime.today().date()

    if "search_box" in request.form:
        search_term = request.form["search_box"].lower()
        search_results = server.get_reg_codes_search_results(search_term)

        return render_template("/admin/regcodes.html", rows=search_results, clear_button=True, page_count=0)
    
    limit = 30
    current_page = 0
    page_count = math.ceil(server.get_reg_code_count() / limit)

    if "last_page_btn" in request.form:
        current_page = page_count - 1

    offset = current_page * limit
    rows = server.construct_reg_code_list(limit, offset)

    if "switch_page_btn" in request.form:
        current_page = int(request.form["switch_page_btn"]) - 1
        if current_page >= 0 and current_page <= page_count:
            offset = current_page * limit
            rows = server.construct_reg_code_list(limit, offset)
            return render_template("/admin/regcodes.html", rows=rows, page_count=page_count, current_page=current_page+1)

    if "clear_btn" in request.form:
        return render_template("/admin/regcodes.html", rows=rows, page_count=page_count, current_page=current_page+1)

    if "add_key_btn" in request.form:
        return redirect("/admin/add-regcode")

    return render_template("/admin/regcodes.html", rows=rows, page_count=page_count, current_page=current_page+1)

@admin.route("/admin/add-regcode", methods=["GET", "POST"])
@login_required
def add_regcode():
    dormitories = server.get_dormitories()

    if request.method == "POST":
        if "cancel_btn" in request.form:
            return redirect("/admin/regcodes")

        if "add_key_btn" in request.form:
            person_id = request.form["person_id"]
            first_name = request.form["first_name"]
            surname = request.form["surname"]
            mail = request.form["mail"]
            dormitory = request.form["dormitory"]
            room = request.form["room"]
            if person_id == "" or first_name == "" or surname == "" or mail == "" or dormitory == "" or room == "":
                flash(_l("Please fill out all input forms."))
                return render_template("/admin/add-regcode.html", dormitories=dormitories)
            else:
                try:
                    dormitory_id = server.get_dormitory_id_from_name(dormitory)
                    reg_key = server.add_registration_code(person_id, first_name, surname, mail, dormitory_id, room)
                    return redirect("/admin/regcodes/" + reg_key)
                except:
                    flash(_l("An error occured while adding the registration code."))
                    return render_template("/admin/add-regcode.html", dormitories=dormitories)

    return render_template("/admin/add-regcode.html", dormitories=dormitories)

@admin.route("/admin/regcodes/<reg_key>/identity/edit", methods=["GET", "POST"])
@login_required
def edit_identity(reg_key):
    identity_data = server.get_reg_code_identity_data(reg_key)
    dormitories = server.get_dormitories()
    current_dormitory_name = server.get_dormitory_name_from_id(identity_data.get("dormitory_id"))
    new_dormitory_name = ""
    if identity_data.get("new_dormitory_id") is not None and identity_data.get("new_dormitory_id") != "":
         new_dormitory_name = server.get_dormitory_name_from_id(identity_data.get("new_dormitory_id"))

    if request.method == "POST":
        if "cancel_btn" in request.form:
            return redirect("/admin/regcodes/" + reg_key)
        
        if "cancel_move_btn" in request.form:
            identity_data["move_date"] = ""
            identity_data["new_dormitory_id"] = None
            identity_data["new_room"] = None
            return render_template("/admin/edit-identity.html",
                                    identity_data=identity_data,
                                    dormitories=dormitories,
                                    current_dormitory_name=current_dormitory_name,
                                    new_dormitory_name=new_dormitory_name)

        if "save_btn" in request.form:
            person_id = request.form["person_id"]
            first_name = request.form["first_name"]
            surname = request.form["surname"]
            mail = request.form["mail"]
            if "dormitory" in request.form.to_dict():
                dormitory_id = server.get_dormitory_id_from_name(request.form["dormitory"])
                room = request.form["room"]
            else:
                dormitory_id = identity_data.get("dormitory_id")
                room = identity_data.get("room")

            try:
                move_date = request.form["move_date"]
            except:
                move_date = ""
            
            if move_date != "":
                if datetime.today().date() >= datetime.strptime(move_date, "%Y-%m-%d").date():
                        flash(_l("Move date must be in the future."))
                        return render_template("/admin/edit-identity.html",
                                                identity_data=identity_data,
                                                dormitories=dormitories,
                                                current_dormitory_name=current_dormitory_name,
                                                new_dormitory_name=new_dormitory_name)

            if person_id == "" or first_name == "" or surname == "" or mail == "" or dormitory_id == "" or room == "":
                flash(_l("Please fill out all input forms."))
                return render_template("/admin/edit-identity.html",
                                        identity_data=identity_data,
                                        dormitories=dormitories,
                                        current_dormitory_name=current_dormitory_name,
                                        new_dormitory_name=new_dormitory_name)
            elif identity_data.get("room") == room and identity_data.get("dormitory_id") == dormitory_id and move_date != "":
                flash(_l("You can not schedule a move if the room and dormitory will stay the same."))
                return render_template("/admin/edit-identity.html",
                                        identity_data=identity_data,
                                        dormitories=dormitories,
                                        current_dormitory_name=current_dormitory_name,
                                        new_dormitory_name=new_dormitory_name)
            else:
                show_deregister_devices_page = False
                if identity_data.get("room") != room or identity_data.get("dormitory_id") != dormitory_id:
                    show_deregister_devices_page = True

                identity_data["person_id"] = person_id
                identity_data["first_name"] = first_name
                identity_data["last_name"] = surname
                identity_data["mail"] = mail
                identity_data["dormitory_id"] = dormitory_id
                identity_data["room"] = room
                identity_data["deletion_date"] = move_date
                if "move_date" in request.form.to_dict():
                    success = server.edit_reg_key_identity(reg_key, person_id, first_name, surname, mail, dormitory_id, room, move_date)
                else:
                    room = identity_data.get("new_room")
                    move_date = identity_data.get("scheduled_move")
                    success = server.edit_reg_key_identity(reg_key, person_id, first_name, surname, mail, dormitory_id, room, move_date)
                if not success:
                    flash(_l("Identity could not get changed."))

                if show_deregister_devices_page is False:
                    return redirect("/admin/regcodes/" + reg_key)
                else:
                    return redirect("/admin/regcodes/" + reg_key + "/deregister-devices")

    return render_template("/admin/edit-identity.html",
                            identity_data=identity_data,
                            dormitories=dormitories,
                            current_dormitory_name=current_dormitory_name,
                            new_dormitory_name=new_dormitory_name)

@admin.route("/admin/regcodes/<reg_key>/deregister-devices", methods=["GET", "POST"])
@login_required
def deregister_devices_dialog_reg_code(reg_key):
    if "no_btn" in request.form:
        return redirect("/admin/regcodes/" + reg_key)

    if "yes_btn" in request.form:
        server.deregister_all_devices(reg_key)
        return redirect("/admin/regcodes/" + reg_key)

    return render_template("/admin/deregister-devices.html")

@admin.route("/admin/regcodes/<reg_key>/deactivate", methods=["GET", "POST"])
@login_required
def deactivate_reg_code(reg_key):
    if request.method == "POST":
        if "cancel_btn" in request.form:
            return redirect("/admin/regcodes/" + reg_key)
        
        if "deactivate_btn" in request.form:
            deactivation_reason = request.form["deactivation_reason"]
            if len(deactivation_reason) > 250:
                flash(_l("Error: Maximum number of characters exceeded."))
                return render_template("/admin/deactivate-regcode.html")
            
            if deactivation_reason == "":
                deactivation_reason = None
        
            success = server.set_reg_key_deactivated(reg_key, deactivation_reason)

            if not success:
                flash(_l("An error occured."))

            return redirect("/admin/regcodes/" + reg_key)
    
    return render_template("/admin/deactivate-regcode.html")

@admin.route("/admin/regcodes/<reg_key>/delete/<ip_address>", methods=["GET", "POST"])
@login_required
def delete_device(reg_key, ip_address):
    if not current_user.is_admin() and not current_user.is_helpdesk():
        return redirect("/admin/dashboard")

    server.deregister_device(ip_address)
    flash(_l("Device unregistered"))
    return redirect("/admin/regcodes/" + reg_key)

@admin.route("/admin/bulk_download_pdf")
def bulk_download_pdf():
    zipf = zipfile.ZipFile("/tmp/bulk_instructions.zip", "w", zipfile.ZIP_DEFLATED)

    reg_keys_rows = server.construct_reg_code_list(500, 0)
    max_saved_volume, initial_volume, daily_topup_volume, shaping_speed, traffy_ip, traffy_domain, max_devices = server.get_instruction_pdf_values()
    creation_date = str(int(time.time()))
    for row in reg_keys_rows:
        reg_key = row["reg_key"]
        first_name, last_name, room = server.get_reg_code_identity(reg_key)
    
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
                                    current_user=current_user,
                                    community=config.COMMUNITY)

        file_path = "/tmp/" + last_name + ", " + first_name + ", " + room + ".pdf"
        with open(file_path, "wb") as fh:
            fh.write(HTML(string=html).write_pdf())
        
        zipf.write(file_path, "/" + last_name + ", " + first_name + ", " + room + ".pdf")
        print("Created " + last_name + ", " + first_name + ", " + room + ".pdf")
    
    zipf.close()
    return send_file('/tmp/bulk_instructions.zip',
            mimetype = 'zip',
            attachment_filename= 'bulk_instructions.zip',
            as_attachment = True)

@admin.route("/admin/regcodes/<reg_key>", methods=["GET", "POST"])
@login_required
def reg_code(reg_key):
    if server.reg_key_exists(reg_key) is False:
        flash(_l("Invalid registration key."))
        return redirect("/admin/regcodes")

    # User Settings Post Processing
    if request.method == "POST":
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
                                   current_user=current_user,
                                   community=config.COMMUNITY)

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
            return redirect("/admin/regcodes/" + reg_key + "/deactivate")

        # Delete Registration Code
        if "delete_code" in request.form:
            success = server.delete_registration_key(reg_key, request.form["delete_code_date"])

            if not success:
                flash(_l("An error occured."))
            else:
                if request.form["delete_code_date"] == "":
                    flash(_l("Registration key successfully deleted."), "success")
                else:
                    flash(_l("Registration key deletion scheduled successfully."), "success")

            if request.form["delete_code_date"] == "":
                return redirect("/admin/regcodes")
            else:
                return redirect("/admin/regcodes/" + reg_key)
        
        # Cancel Pending Registration Code Deletion
        if "cancel_delete_code" in request.form:
            success = server.cancel_delete_registration_key(reg_key)

            if not success:
                flash(_l("An error occured."))
            else:
                flash(_l("Canceled pending registration key deletion."), "success")

            return redirect("/admin/regcodes/" + reg_key)

    # Statistics
    legend_downlink = "↓ "  + _l("Accounted")
    legend_downlink_unlimited_range = "↓ " + _l("Timerule")
    legend_downlink_shaped = "↓ " + _l("Shaped")
    legend_downlink_excepted = "↓ " + _l("Exceptions")
    legend_uplink = "↑ " + _l("Accounted")
    legend_uplink_unlimited_range = "↑ " + _l("Timerule")
    legend_uplink_shaped = "↑ " + _l("Shaped")
    legend_uplink_excepted = "↑ " + _l("Exceptions")
    stat_volume_left, stat_created_on, stat_shaped, stat_status, labels, values_downlink, values_downlink_unlimited_range, values_downlink_shaped, values_downlink_excepted, values_uplink, values_uplink_unlimited_range, values_uplink_shaped, values_uplink_excepted = server.get_reg_code_statistics(reg_key)

    if stat_shaped:
        stat_shaped = _l("Yes")
    else:
        stat_shaped = _l("No")

    if stat_status:
        stat_status = _l("Enabled")
    else:
        stat_status = _l("Disabled")

    # Identity
    identity_data = server.get_reg_code_identity_data(reg_key)

    # Devices
    device_list = server.get_reg_code_device_list(reg_key)

    # User Settings Variables
    custom_volume_enabled, value_custom_topup, custom_max_enabled, value_max_volume, accounting_enabled, key_active, deletion_date = server.get_reg_code_settings_values(reg_key)

    # Deactivation Reason
    if key_active is False:
        deactivation_reason = server.get_reg_key_deactivation_reason(reg_key)
    else:
        deactivation_reason = NotImplemented

    # Room
    room = server.get_reg_code_room(reg_key)

    return render_template("/admin/key-page.html",
                           reg_key=reg_key,
                           stat_volume_left=stat_volume_left,
                           stat_created_on=stat_created_on,
                           stat_shaped=stat_shaped,
                           stat_status=stat_status,
                           labels=labels,
                           values_downlink=values_downlink,
                           values_downlink_unlimited_range=values_downlink_unlimited_range,
                           values_downlink_shaped=values_downlink_shaped,
                           values_downlink_excepted=values_downlink_excepted,
                           values_uplink=values_uplink,
                           values_uplink_unlimited_range=values_uplink_unlimited_range,
                           values_uplink_shaped=values_uplink_shaped,
                           values_uplink_excepted=values_uplink_excepted,
                           legend_downlink=legend_downlink,
                           legend_downlink_unlimited_range=legend_downlink_unlimited_range,
                           legend_downlink_shaped=legend_downlink_shaped,
                           legend_downlink_excepted=legend_downlink_excepted,
                           legend_uplink=legend_uplink,
                           legend_uplink_unlimited_range=legend_uplink_unlimited_range,
                           legend_uplink_shaped=legend_uplink_shaped,
                           legend_uplink_excepted=legend_uplink_excepted,
                           identity_data=identity_data,
                           device_list=device_list,
                           custom_volume_enabled=custom_volume_enabled,
                           value_custom_topup=value_custom_topup,
                           custom_max_enabled=custom_max_enabled,
                           value_max_volume=value_max_volume,
                           accounting_enabled=accounting_enabled,
                           key_active=key_active,
                           room=room,
                           deactivation_reason=deactivation_reason,
                           deletion_date=deletion_date)

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
        return render_template("/admin/infrastructure.html", rows=rows)

    if "add_key_btn" in request.form:
        return redirect("/admin/add-regcode")

    return render_template("/admin/infrastructure.html", rows=rows)

@admin.route("/admin/notifications", methods=["GET", "POST"])
@login_required
def notifications():
    rows = []
    for row in Notification.query.all():
        rows.append(NotificationRow(row.id, row.title, row.body, row.display_from, row.display_until))

    if request.method == "POST":
        if "create_notification_btn" in request.form:
            return redirect("/admin/create-notification")

    return render_template("/admin/notifications.html", rows=rows)

@admin.route("/admin/create-notification", methods=["GET", "POST"])
@login_required
def create_notification():
    if request.method == "POST":
        if "cancel_btn" in request.form:
            return redirect("/admin/notifications")

        if "create_btn" in request.form:
            title = request.form["title"]
            body = request.form["body"]
            valid_from = request.form["valid_from"]
            valid_until = request.form["valid_until"]
            
            if valid_from != "" and valid_until != "":
                if datetime.strptime(valid_from, "%Y-%m-%d").date() > datetime.strptime(valid_until, "%Y-%m-%d").date():
                        flash(_l("The notification cant be invalid before its valid time."))
                        return render_template("/admin/create-notification.html")

            if title == "" or body == "" or valid_from == "" and valid_until == "":
                flash(_l("Please fill out all input forms."))
                return render_template("/admin/create-notification.html")
            else:
                success = notification_functions.create_notification(title, body, valid_from, valid_until)
                if not success:
                    flash(_l("Notification could not get created."))
                return redirect("/admin/notifications")

    return render_template("/admin/create-notification.html")

@admin.route("/admin/notifications/edit/<notification_id>", methods=["GET", "POST"])
@login_required
def edit_notification(notification_id):
    if request.method == "POST":
        if "cancel_btn" in request.form:
            return redirect("/admin/notifications")

        if "save_btn" in request.form:
            title = request.form["title"]
            body = request.form["body"]
            valid_from = request.form["valid_from"]
            valid_until = request.form["valid_until"]
            
            if valid_from != "" and valid_until != "":
                if datetime.strptime(valid_from, "%Y-%m-%d").date() > datetime.strptime(valid_until, "%Y-%m-%d").date():
                        flash(_l("The notification cant be invalid before its valid time."))
                        return render_template("/admin/create-notification.html")

            if title == "" or body == "" or valid_from == "" and valid_until == "":
                flash(_l("Please fill out all input forms."))
                return render_template("/admin/create-notification.html")
            else:
                success = notification_functions.edit_notification(notification_id, title, body, valid_from, valid_until)
                if not success:
                    flash(_l("Notification could not get edited."))
                return redirect("/admin/notifications")

    notification_data = notification_functions.get_notification_data(notification_id)

    if notification_data is None:
        flash(_l("Notification does not exist."))
        return redirect("/admin/notifications")

    return render_template("/admin/edit-notification.html", notification_data=notification_data)


@admin.route("/admin/notifications/delete/<notification_id>", methods=["GET", "POST"])
@login_required
def delete_notification(notification_id):
    success = notification_functions.delete_notification(notification_id)

    if success:
        flash(_l("Notification deleted"))
    else:
        flash(_l("An error occured while deleting the notification"))

    return redirect("/admin/notifications")

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

class NotificationRow():
    id = NotImplemented
    title = ""
    body = ""
    display_from = NotImplemented
    display_until = NotImplemented

    def __init__(self, id, title, body, display_from, display_until):
        self.id = id
        self.title = title
        self.body = body
        self.display_from = display_from.strftime("%d.%m.%Y")
        self.display_until = display_until.strftime("%d.%m.%Y")
