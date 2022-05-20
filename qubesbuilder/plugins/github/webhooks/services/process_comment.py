#!/usr/bin/python3
# -*- encoding: utf8 -*-
#
# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2017 Marek Marczykowski-Górecki <marmarek@invisiblethingslab.com>
# Copyright (C) 2020 Frédéric Pierret <frederic.pierret@qubes-os.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import sys
import subprocess
import os
import re

_trailing_space = re.compile(rb"[ \r\t\f\v]*\n")


class Service:
    def __init__(self):
        self.config_path = os.path.join(
            os.environ.get("HOME", "/"),
            ".config",
            "qubes-builder-github",
            "build-vms.list",
        )

    def qrexec(self, vm, service, input_data=None):
        with subprocess.Popen(
            ["/usr/bin/qrexec-client-vm", "--", vm, service],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
        ) as p:
            p.communicate(input_data)

    def handle(self, obj):
        try:
            if obj["action"] != "created":
                return
            comment_body = obj["comment"]["body"]
        except (TypeError, KeyError):
            return
        if type(comment_body) is not str:
            return
        try:
            comment_body = comment_body.encode("ascii", "strict")
        except UnicodeEncodeError:
            return  # ignore non-ASCII commands

        # strip trailing space, including carriage returns
        comment_body = _trailing_space.subn(b"\n", comment_body)[0]

        # skip comment not having signed part at all
        try:
            offset = comment_body.index(b"-----BEGIN PGP SIGNED MESSAGE-----\nHash: ")
        except ValueError:
            return
        comment_body = comment_body[offset:]
        end_index = b"\n-----END PGP SIGNATURE-----"
        try:
            offset = comment_body.index(end_index)
        except ValueError:
            return
        # strip stuff after signature and add trailing newline
        comment_body = comment_body[: offset + len(end_index)] + b"\n"
        try:
            with open(self.config_path) as config:
                build_vms = config.read().splitlines()
        except IOError as e:
            print(str(e), file=sys.stderr)
            return
        for vm in build_vms:
            self.qrexec(vm, "qubesbuilder.ProcessGithubCommand", comment_body)
