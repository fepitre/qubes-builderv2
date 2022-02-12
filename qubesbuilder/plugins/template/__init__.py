# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2022 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
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
from qubesbuilder.template import QubesTemplate
from qubesbuilder.executors import Executor
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import Plugin, PluginError

log = get_logger("template")


class TemplateError(PluginError):
    pass


class TemplatePlugin(Plugin):
    """
    TemplatePlugin manages distribution build.
    """

    def __init__(self, component: QubesComponent, template: QubesTemplate, executor: Executor,
                 plugins_dir: Path, artifacts_dir: Path, verbose: bool = False,
                 debug: bool = False):
        super().__init__(component=component, dist=template.distribution, plugins_dir=plugins_dir,
                         artifacts_dir=artifacts_dir, verbose=verbose, debug=debug)

        self.executor = executor
        self.verbose = verbose
        self.debug = debug

    def run(self, stage: str):
        pass
