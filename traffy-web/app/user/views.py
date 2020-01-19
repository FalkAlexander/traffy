from flask import Flask, render_template, request, flash, session, redirect
from flask_babel import lazy_gettext as _l
from . import user
from .. import server, babel
import config



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

    user = server.access_check(ip_address)
    if user.get("registered") is False:
        return redirect("/register", code=307)
    elif user.get("registered") is True:
        return redirect("/dashboard", code=307)
    elif user.get("deactivated") is True:
        return render_template("errors/deactivated.html")
    elif user.get("ip_stolen") is True:
        return render_template("errors/ip_stolen.html")

@user.route("/register", methods=["GET", "POST"])
def register():
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

    user = server.access_check(ip_address)
    if user.get("registered") is True:
        return redirect("/dashboard", code=307)
    elif user.get("deactivated") is True:
        return render_template("errors/deactivated.html")
    elif user.get("ip_stolen") is True:
        return render_template("errors/ip_stolen.html")

    __init_session_variables()

    if request.method != "POST" and "register_btn" not in request.form:
        return render_template("user/register.html")

    reg_key = request.form["key"].lower()
    if __reg_key_check(reg_key) is False:
        flash(_l("Invalid registration key.") + " Code: 100")
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
    user = server.access_check(ip_address)

    if user.get("registered") is True:
        return redirect("/dashboard", code=307)
    elif user.get("deactivated") is True:
        return render_template("errors/deactivated.html")
    elif user.get("ip_stolen") is True:
        return render_template("errors/ip_stolen.html")

    reg_key = session.get("reg_key")
    if __reg_key_check(reg_key) is False:
        flash(_l("Invalid registration key.") + " Code: 100")
        return render_template("user/register.html")

    if "accept_btn" not in request.form:
        return render_template("user/conditions.html")

    ip_address = session.get("ip_address")
    server.register_device(reg_key, ip_address, request.headers.get("User-Agent"))

    return redirect("/dashboard", code=307)

@user.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)
    user = server.access_check(ip_address)

    if user.get("registered") is False:
        return redirect("/register", code=307)
    elif user.get("deactivated") is True:
        return render_template("errors/deactivated.html")
    elif user.get("ip_stolen") is True:
        return render_template("errors/ip_stolen.html")

    __init_session_variables()

    ip_address = session.get("ip_address")

    volume_left, credit = server.get_reg_key_credit_by_ip(ip_address)

    user_agent = request.headers.get("User-Agent")
    #server.set_device_user_agent(ip_address, user_agent)

    if "reedem_dashboard_btn" in request.form:
        return redirect("/reedem", code=307)

    if "deregister_dashboard_btn" in request.form:
        return redirect("/deregister", code=307)

    return render_template("user/dashboard.html", volume_left=volume_left, credit=credit)

@user.route("/reedem", methods=["POST"])
def reedem():
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)
    user = server.access_check(ip_address)

    if user.get("registered") is False:
        return redirect("/register", code=307)
    elif user.get("deactivated") is True:
        return render_template("errors/deactivated.html")
    elif user.get("ip_stolen") is True:
        return render_template("errors/ip_stolen.html")

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
    user = server.access_check(ip_address)

    if user.get("registered") is False:
        return redirect("/register", code=307)
    elif user.get("deactivated") is True:
        return render_template("errors/deactivated.html")
    elif user.get("ip_stolen") is True:
        return render_template("errors/ip_stolen.html")

    if "deregister_btn" in request.form:
        ip_address = session.get("ip_address")
        server.deregister_device(ip_address)

        return redirect("/register")

    return render_template("user/deregister.html")

@user.route("/about", methods=["GET", "POST"])
def about():
    return render_template("user/about.html")

#
# Private
#

def __init_session_variables():
    session["ip_address"] = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

def __reg_key_check(reg_key):
    if reg_key == "" or server.reg_key_exists(reg_key) is False:
        return False
    return True

