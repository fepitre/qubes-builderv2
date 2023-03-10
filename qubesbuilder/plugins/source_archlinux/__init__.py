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

import shutil
import tempfile
from pathlib import Path

from qubesbuilder.common import is_filename_valid
from qubesbuilder.component import QubesComponent
from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import ExecutorError
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import ArchlinuxDistributionPlugin
from qubesbuilder.plugins.source import SourcePlugin, SourceError

log = get_logger("source_archlinux")


class ArchLinuxSourcePlugin(ArchlinuxDistributionPlugin, SourcePlugin):
    """
    Manage Archlinux distribution source.
    """

    stages = ["prep"]
    dependencies = ["fetch", "source"]

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        config: Config,
        manager: PluginManager,
        **kwargs,
    ):
        super().__init__(component=component, dist=dist, config=config, manager=manager)

        self.environment.update({"DIST": self.dist.name, "LC_ALL": "C"})

    def run(self, stage: str):
        """
        Run plugin for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage != "prep" or not self.has_component_packages("prep"):
            return

        executor = self.config.get_executor_from_config(stage)
        parameters = self.get_parameters(stage)

        # Check if we have Archlinux related content defined
        if not parameters.get("build", []):
            log.info(f"{self.component}:{self.dist}: Nothing to be done.")
            return

        # Compare previous artifacts hash with current source hash
        if all(
            self.component.get_source_hash()
            == self.get_dist_artifacts_info(stage, build.mangle()).get(
                "source-hash", None
            )
            for build in parameters["build"]
        ):
            log.info(
                f"{self.component}:{self.dist}: Source hash is the same than already prepared source. Skipping."
            )
            return

        # Get fetch info
        fetch_info = self.get_dist_artifacts_info(
            "fetch",
            "source",
            artifacts_dir=self.get_component_artifacts_dir("fetch"),
        )

        artifacts_dir = self.get_dist_component_artifacts_dir(stage)

        # Clean previous build artifacts
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir.as_posix())
        artifacts_dir.mkdir(parents=True)

        for build in parameters["build"]:
            # Temporary dir for temporary copied-out files
            temp_dir = Path(tempfile.mkdtemp())

            # Source component directory inside executors
            source_dir = executor.get_builder_dir() / self.component.name

            # spec file basename will be used as prefix for some artifacts
            build_bn = build.mangle()

            # Generate %{name}-%{version}-%{release} and %Source0
            copy_in = [
                (self.component.source_dir, executor.get_builder_dir()),
                (
                    self.manager.entities["source_archlinux"].directory,
                    executor.get_plugins_dir(),
                ),
            ] + [
                (
                    self.manager.entities[dependency].directory,
                    executor.get_plugins_dir(),
                )
                for dependency in self.dependencies
            ]

            copy_out = [
                (source_dir / f"{build_bn}_packages.list", temp_dir),
            ]

            # if self.config.increment_devel_versions:
            #     dist_tag = f"{self.component.devel}.{self.dist.tag}"
            # else:
            #     dist_tag = self.dist.tag

            cmd = [
                f"{executor.get_plugins_dir()}/source_archlinux/scripts/get-source-info "
                f"{source_dir} {source_dir / build}"
            ]
            try:
                executor.run(cmd, copy_in, copy_out, environment=self.environment)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}:{build}: Failed to get source information: {str(e)}."
                raise SourceError(msg) from e

            # Read packages list
            packages_list = []
            with open(temp_dir / f"{build_bn}_packages.list") as f:
                data = f.read().splitlines()
            for line in data:
                if not is_filename_valid(line):
                    msg = f"{self.component}:{self.dist}:{build}: Invalid package name."
                    raise SourceError(msg)
                pkg = f"{line}-{self.component.verrel}-{self.dist.architecture}.pkg.tar.zst"
                packages_list.append(pkg)

            # Save package information we parsed for next stages
            try:
                info = fetch_info
                info.update(
                    {
                        "pkgs": packages_list,
                        "source-hash": self.component.get_source_hash(),
                    }
                )
                self.save_dist_artifacts_info(stage=stage, basename=build_bn, info=info)

                # Clean temporary directory
                shutil.rmtree(temp_dir)
            except OSError as e:
                msg = f"{self.component}:{self.dist}:{build}: Failed to clean artifacts: {str(e)}."
                raise SourceError(msg) from e


PLUGINS = [ArchLinuxSourcePlugin]
