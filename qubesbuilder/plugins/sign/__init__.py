# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2021 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
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
# with this program. If not, see <https://www.gnu.org/licenses/>.
#
# SPDX-License-Identifier: GPL-3.0-or-later

from pathlib import Path

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import Plugin, PluginException

log = get_logger("sign")


class SignException(PluginException):
    pass


class SignPlugin(Plugin):
    """
    SignPlugin manages generic distribution sign.
    """

    def __init__(self, component: QubesComponent, dist: QubesDistribution, executor: Executor, plugins_dir: Path,
                 artifacts_dir: Path, gpg_client: str, sign_key: dict,
                 verbose: bool = False, debug: bool = False):
        super().__init__(component=component, dist=dist, plugins_dir=plugins_dir,
                         artifacts_dir=artifacts_dir, verbose=verbose, debug=debug)

        self.executor = executor
        self.verbose = verbose
        self.debug = debug
        self.gpg_client = gpg_client
        self.sign_key = sign_key

    def run(self, stage: str):
        if stage == "publish" and not isinstance(self.executor, LocalExecutor):
            raise SignException("This plugin only supports local executor.")
