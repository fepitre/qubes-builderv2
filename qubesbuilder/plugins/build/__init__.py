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
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import DistributionPlugin, PluginError

log = get_logger("build")


class BuildError(PluginError):
    pass


class BuildPlugin(DistributionPlugin):
    """
    BuildPlugin manages generic distribution build.
    """

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        backend_vmm: str,
        verbose: bool = False,
        debug: bool = False,
        use_qubes_repo: dict = None,
    ):
        super().__init__(
            component=component,
            dist=dist,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
            backend_vmm=backend_vmm,
        )
        self.executor = executor
        self.use_qubes_repo = use_qubes_repo or {}

    def run(self, stage: str):
        if stage != "build":
            return

        # Check if we have Debian related content defined
        if not self.parameters.get("build", []):
            log.info(f"{self.component}:{self.dist}: Nothing to be done.")
            return

        # Ensure all build targets artifacts exist from previous required stage
        try:
            self.check_dist_stage_artifacts(stage="prep")
        except PluginError as e:
            raise BuildError(str(e)) from e
