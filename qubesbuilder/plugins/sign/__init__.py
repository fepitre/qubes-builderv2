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

from qubesbuilder.component import QubesComponent
from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.plugins import DistributionComponentPlugin, PluginError


class SignError(PluginError):
    pass


class SignPlugin(DistributionComponentPlugin):
    """
    SignPlugin manages generic distribution sign.

    Stages:
        - sign - Ensure all build targets artifacts exist from previous required stages.

    Entry points:
        - build
    """

    name = "sign"

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        config: Config,
        manager: PluginManager,
        executor: Executor,
        **kwargs,
    ):
        super().__init__(
            component=component,
            dist=dist,
            config=config,
            manager=manager,
            executor=executor,
        )

    def run(self, stage: str):
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage != "sign" or not self.has_component_packages("sign"):
            return

        # Check if we have Debian related content defined
        if not self.get_parameters(stage).get("build", []):
            self.log.info(f"{self.component}:{self.dist}: Nothing to be done.")
            return

        if not isinstance(self.executor, LocalExecutor):
            raise SignError("This plugin only supports local executor.")

        # Ensure all build targets artifacts exist from previous required stage
        try:
            self.check_dist_stage_artifacts(stage="build")
        except PluginError as e:
            raise SignError(str(e)) from e
