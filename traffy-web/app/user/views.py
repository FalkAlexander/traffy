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

from git import Repo
from flask import Flask, render_template, request, flash, session, redirect, make_response
from flask_babel import lazy_gettext as _l
from . import user, notification_functions
from .. import server, babel, client_version
import config
import json
import os



#
# Locale Initialization
#

@babel.localeselector
def get_locale():
    return request.accept_languages.best_match(config.LANGUAGES)

#
# Routes
#

@user.route("/", methods=["GET"])
def index():
    __init_session_variables()

    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

    try:
        user = server.access_check(ip_address)
    except ConnectionRefusedError:
        return render_template("errors/backend_lost.html")
    
    redirect_value = __route_manager(user, ip_address)
    if redirect_value is not None:
        return redirect_value

@user.route("/register", methods=["GET", "POST"])
def register():
    if config.STATELESS:
        branch_name, commits = __get_developer_infos()
        return redirect("/about")

    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

    try:
        user = server.access_check(ip_address)
    except ConnectionRefusedError:
        return render_template("errors/backend_lost.html")

    redirect_value = __route_manager(user, ip_address, restricted_area=False)
    if redirect_value is not None:
        return redirect_value

    __init_session_variables()

    if request.method != "POST" and "register_btn" not in request.form:
        return render_template("user/register.html")

    reg_key = request.form["key"].lower()
    if __reg_key_check(reg_key) is False:
        flash(_l("Invalid registration key.") + " Code: 100")
        return render_template("user/register.html")

    if server.is_reg_key_deactivated(reg_key) is True:
        deactivation_reason = server.get_reg_key_deactivation_reason(reg_key)
        if deactivation_reason is None:
            flash(_l("Your registration key got deactivated. Please contact the administrator."))
        else:
            flash(_l("Your registration key got deactivated. Reason: ") + deactivation_reason)
        return render_template("user/register.html")

    devices_count = server.get_registered_devices_count(reg_key)
    if devices_count >= server.get_maximum_allowed_devices():
        flash(_l("Maximum number of devices already registered.") + " Code: 110")
        return render_template("user/register.html")

    session["reg_key"] = reg_key
    return redirect("/conditions", code=307)

@user.route("/conditions", methods=["POST"])
def conditions():
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

    try:
        user = server.access_check(ip_address)
    except ConnectionRefusedError:
        return render_template("errors/backend_lost.html")

    redirect_value = __route_manager(user, ip_address, restricted_area=False)
    if redirect_value is not None:
        return redirect_value

    reg_key = session.get("reg_key")
    if __reg_key_check(reg_key) is False:
        flash(_l("Invalid registration key.") + " Code: 100")
        return render_template("user/register.html")
    
    if server.is_reg_key_deactivated(reg_key) is True:
        deactivation_reason = server.get_reg_key_deactivation_reason(reg_key)
        if deactivation_reason is None:
            flash(_l("Your registration key got deactivated. Please contact the administrator."))
        else:
            flash(_l("Your registration key got deactivated. Reason: ") + deactivation_reason)
        return render_template("user/register.html")

    if "accept_eula_btn" not in request.form:
        return render_template("user/conditions.html")

    server.set_eula_accepted(reg_key)

    return redirect("/privacy-policy", code=307)

@user.route("/privacy-policy", methods=["POST"])
def privacy_policy():
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

    try:
        user = server.access_check(ip_address)
    except ConnectionRefusedError:
        return render_template("errors/backend_lost.html")

    redirect_value = __route_manager(user, ip_address, restricted_area=False)
    if redirect_value is not None:
        return redirect_value

    reg_key = session.get("reg_key")
    if __reg_key_check(reg_key) is False:
        flash(_l("Invalid registration key.") + " Code: 100")
        return render_template("user/register.html")
    
    if server.is_reg_key_deactivated(reg_key) is True:
        deactivation_reason = server.get_reg_key_deactivation_reason(reg_key)
        if deactivation_reason is None:
            flash(_l("Your registration key got deactivated. Please contact the administrator."))
        else:
            flash(_l("Your registration key got deactivated. Reason: ") + deactivation_reason)
        return render_template("user/register.html")

    if "accept_privacy_policy_btn" not in request.form:
        return render_template("user/privacy_policy.html")

    ip_address = session.get("ip_address")
    server.set_data_policy_accepted(reg_key)
    server.register_device(reg_key, ip_address, request.headers.get("User-Agent"))

    return redirect("/dashboard", code=307)

@user.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

    try:
        user = server.access_check(ip_address)
    except ConnectionRefusedError:
        return render_template("errors/backend_lost.html")

    redirect_value = __route_manager(user, ip_address, restricted_area=True)
    if redirect_value is not None:
        return redirect_value

    __init_session_variables()

    ip_address = session.get("ip_address")

    volume_left, max_volume = server.get_reg_key_credit_by_ip(ip_address)
    in_unlimited_time_range = server.get_in_unlimited_time_range()

    notifications = notification_functions.get_display_notifications()
    if "hidden_notifications" in request.cookies:
        try:
            hidden_list = json.loads(request.cookies.get("hidden_notifications"))

            for hidden_notification in hidden_list:
                for notification in notifications:
                    if hidden_notification == str(notification.id):
                        notifications.remove(notification)
        except:
            pass

    if "switch_ui_advanced" in request.form:
        legend_downlink = "↓ " + _l("Accounted")
        legend_downlink_unlimited_range = "↓ " + _l("Timerule")
        legend_downlink_shaped = "↓ " + _l("Shaped")
        legend_downlink_excepted = "↓ " + _l("Exceptions")
        legend_uplink = "↑ " + _l("Accounted")
        legend_uplink_unlimited_range = "↑ " + _l("Timerule")
        legend_uplink_shaped = "↑ " + _l("Shaped")
        legend_uplink_excepted = "↑ " + _l("Exceptions")

        values_downlink, values_downlink_unlimited_range, values_downlink_shaped, values_downlink_excepted, values_uplink, values_uplink_unlimited_range, values_uplink_shaped, values_uplink_excepted, labels = server.get_advanced_dashboard_stats(ip_address)

        device_list = server.get_reg_code_device_list_by_ip(ip_address)
        identity_data = server.get_reg_code_identity_data_by_ip(ip_address)

        return render_template("user/dashboard_advanced.html", volume_left=volume_left,
                                                                max_volume=max_volume,
                                                                in_unlimited_time_range=in_unlimited_time_range,
                                                                values_downlink=values_downlink,
                                                                values_downlink_unlimited_range=values_downlink_unlimited_range,
                                                                values_downlink_shaped=values_downlink_shaped,
                                                                values_downlink_excepted=values_downlink_excepted,
                                                                values_uplink=values_uplink,
                                                                values_uplink_unlimited_range=values_uplink_unlimited_range,
                                                                values_uplink_shaped=values_uplink_shaped,
                                                                values_uplink_excepted=values_uplink_excepted,
                                                                labels=labels,
                                                                legend_downlink=legend_downlink,
                                                                legend_downlink_unlimited_range=legend_downlink_unlimited_range,
                                                                legend_downlink_shaped=legend_downlink_shaped,
                                                                legend_downlink_excepted=legend_downlink_excepted,
                                                                legend_uplink=legend_uplink,
                                                                legend_uplink_unlimited_range=legend_uplink_unlimited_range,
                                                                legend_uplink_shaped=legend_uplink_shaped,
                                                                legend_uplink_excepted=legend_uplink_excepted,
                                                                device_list=device_list,
                                                                identity_data=identity_data,
                                                                notifications=notifications)

    if "switch_ui_basic" in request.form:
        return render_template("user/dashboard.html", volume_left=volume_left, max_volume=max_volume, in_unlimited_time_range=in_unlimited_time_range, notifications=notifications)
    
    if "mark_msg_read" in request.form:
        notification_id = request.form["mark_msg_read"]

        for notification in notifications:
            if str(notification.id) == notification_id:
                notifications.remove(notification)

        resp = make_response(render_template("user/dashboard.html", volume_left=volume_left, max_volume=max_volume, in_unlimited_time_range=in_unlimited_time_range, notifications=notifications))

        if "hidden_notifications" not in request.cookies:
            resp.set_cookie("hidden_notifications", json.dumps([notification_id]), secure=True, httponly=True)
        else:
            try:
                hidden_list = json.loads(request.cookies.get("hidden_notifications"))
                if notification_id not in hidden_list:
                    hidden_list.append(notification_id)
                    resp.set_cookie("hidden_notifications", json.dumps(hidden_list), secure=True, httponly=True)
            except:
                pass

        return resp

    if "reedem_dashboard_btn" in request.form:
        return redirect("/reedem", code=307)

    if "deregister_dashboard_btn" in request.form:
        return redirect("/deregister", code=307)

    return render_template("user/dashboard.html", volume_left=volume_left, max_volume=max_volume, in_unlimited_time_range=in_unlimited_time_range, notifications=notifications)

@user.route("/reedem", methods=["POST"])
def reedem():
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

    try:
        user = server.access_check(ip_address)
    except ConnectionRefusedError:
        return render_template("errors/backend_lost.html")

    redirect_value = __route_manager(user, ip_address, restricted_area=True)
    if redirect_value is not None:
        return redirect_value

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
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

    try:
        user = server.access_check(ip_address)
    except ConnectionRefusedError:
        return render_template("errors/backend_lost.html")

    redirect_value = __route_manager(user, ip_address, restricted_area=True)
    if redirect_value is not None:
        return redirect_value

    if "deregister_btn" in request.form:
        ip_address = session.get("ip_address")
        server.deregister_device(ip_address)

        return redirect("/register")

    return render_template("user/deregister.html")

@user.route("/about", methods=["GET", "POST"])
def about():
    branch_name, commits = __get_developer_infos()

    return render_template("user/about.html", branch_name=branch_name, commits=commits, external=False)

#
# Private
#

def __init_session_variables():
    session["ip_address"] = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

def __reg_key_check(reg_key):
    if reg_key == "" or server.reg_key_exists(reg_key) is False:
        return False
    return True

def __get_developer_infos():
    repo = Repo(config.GIT_REPO_PATH)
    branch = repo.active_branch
    branch_name = branch.name

    commits = repo.iter_commits(branch, max_count=15)

    return branch_name, commits

def __route_manager(user_access, ip_address, restricted_area=None):
    if restricted_area is None:
        if user_access.get("unregistered") is True:
            return redirect("/register", code=307)

        if user_access.get("registered") is True:
            return redirect("/dashboard", code=307)
    else:
        if restricted_area is True:
            if user_access.get("unregistered") is True:
                return redirect("/register", code=307)
        else:
            if user_access.get("registered") is True:
                return redirect("/dashboard", code=307)

    if user_access.get("outside_lan") is True:
        branch_name, commits = __get_developer_infos()
        return render_template("user/about.html", branch_name=branch_name, commits=commits, external=True)
    
    if user_access.get("no_lease") is True:
        return render_template("errors/no_lease.html")
    
    if user_access.get("error") is True:
        return render_template("errors/500.html")
    
    if user_access.get("deactivated") is True:
        deactivation_reason = server.get_reg_key_deactivation_reason_by_ip(ip_address)
        return render_template("errors/deactivated.html", reason=deactivation_reason)

    if user_access.get("device_registered_with_different_port") is True:
        return render_template("errors/device_registered_with_different_port.html")