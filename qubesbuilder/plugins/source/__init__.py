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
from qubesbuilder.plugins import (
    DistributionComponentPlugin,
    PluginError,
    PluginDependency,
    JobDependency,
)


class SourceError(PluginError):
    pass


class SourcePlugin(DistributionComponentPlugin):
    """
    SourcePlugin manage generic distribution source

    Stages:
        - prep: Check if 'fetch' artifacts info have been created.

    Entry points:
        - source
    """

    name = "source"
    dependencies = [PluginDependency("fetch")]

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        config: Config,
        manager: PluginManager,
        stage: str,
    ):
        super().__init__(
            component=component,
            dist=dist,
            config=config,
            manager=manager,
            stage=stage,
        )
        self.dependencies.append(JobDependency((component.name, "fetch")))

    def update_parameters(self, stage: str):
        super().update_parameters(stage)

        # Set and update parameters based on top-level "source",
        # per package set and per distribution.
        parameters = self.component.get_parameters(self.get_placeholders(stage))

        self._parameters[stage].update(parameters.get("source", {}))
        self._parameters[stage].update(
            parameters.get(self.dist.package_set, {}).get("source", {})
        )
        self._parameters[stage].update(
            parameters.get(self.dist.distribution, {}).get("source", {})
        )

    def run(self):
        # Run stage defined by parent class
        super().run()

        if self.stage != "prep" or not self.has_component_packages("prep"):
            return

        # Compare previous artifacts hash with current source hash
        fetch_info = self.get_dist_artifacts_info(
            "fetch",
            "source",
            artifacts_dir=self.get_component_artifacts_dir("fetch"),
        )

        # Compare previous artifacts hash with current source hash
        if not fetch_info.get("source-hash"):
            raise SourceError(
                f"{self.component}:{self.dist}: Missing 'fetch' stage artifacts!"
            )
