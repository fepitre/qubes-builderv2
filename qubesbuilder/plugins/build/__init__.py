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
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.plugins import DistributionComponentPlugin, PluginError


class BuildError(PluginError):
    pass


class BuildPlugin(DistributionComponentPlugin):
    """
    BuildPlugin manages generic distribution build.

    Stages:
        - build - Ensure all build targets artifacts exist from previous required stage.

    Entry points:
        - build
    """

    name = "build"

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        config: Config,
        manager: PluginManager,
        stage: str
    ):
        super().__init__(
            component=component,
            dist=dist,
            config=config,
            manager=manager,
            stage=stage
        )

    def run(self, stage: str):
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage != "build" or not self.has_component_packages("build"):
            return

        if not self.get_parameters(stage).get("build", []):
            self.log.info(f"{self.component}:{self.dist}: Nothing to be done.")
            return

        # Ensure all build targets artifacts exist from previous required stage
        try:
            self.check_dist_stage_artifacts(stage="prep")
        except PluginError as e:
            raise BuildError(str(e)) from e
