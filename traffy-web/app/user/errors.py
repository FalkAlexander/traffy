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

from flask import render_template, request, jsonify, redirect
from . import user
from .. import server


@user.app_errorhandler(403)
def forbidden(e):
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'forbidden'})
        response.status_code = 403
        return response

    return render_template("errors/403.html"), 403

@user.app_errorhandler(404)
def page_not_found(e):
    ip_address = request.environ.get("HTTP_X_REAL_IP", request.remote_addr)

    try:
        user = server.access_check(ip_address)
    except ConnectionRefusedError:
        return render_template("errors/backend_lost.html")

    if user.get("registered") is False:
        return redirect("/register", code=307)

    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'not found'})
        response.status_code = 404
        return response

    return render_template("errors/404.html"), 404

@user.app_errorhandler(405)
def method_not_allowed(e):
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'not allowed'})
        response.status_code = 405
        return response

    return render_template("errors/405.html"), 405

@user.app_errorhandler(500)
def internal_server_error(e):
    if request.accept_mimetypes.accept_json and \
            not request.accept_mimetypes.accept_html:
        response = jsonify({'error': 'internal server error'})
        response.status_code = 500
        return response

    return render_template("errors/500.html"), 500

