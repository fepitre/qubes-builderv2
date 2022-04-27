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


class Service:
    def __init__(self):
        self.config_path = os.path.join(
            os.environ.get('HOME', '/'),
            '.config',
            'qubes-builder-github',
            'build-vms.list')

    def qrexec(self, vm, service, input_data=None):
        p = subprocess.Popen(['/usr/bin/qrexec-client-vm', vm, service],
                             stdin=subprocess.PIPE,
                             stdout=open(os.devnull, 'w'))
        if input_data is not None:
            p.communicate(input_data)
        else:
            p.stdin.close()

    def handle(self, payload):
        try:
            if 'repository' not in payload:
                return
            repo_name = payload['repository']['full_name']
            prefixed_repo = re.match('.*/qubes-(.*)', repo_name)
            if prefixed_repo:
                repo_name = prefixed_repo.group(1)
            else:
                repo_name = repo_name.split('/')[-1]
            try:
                with open(self.config_path) as config:
                    build_vms = config.read().splitlines()
            except IOError as e:
                print(str(e), file=sys.stderr)
                return
            for vm in build_vms:
                self.qrexec(vm, 'qubesbuilder.TriggerBuild+' + repo_name)
        except KeyError:
            pass

