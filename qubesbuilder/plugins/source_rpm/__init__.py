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

import os
from pathlib import Path

import yaml
import shutil

from qubesbuilder.common import is_filename_valid
from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import BUILDER_DIR, PLUGINS_DIR, BUILD_DIR, DISTFILES_DIR
from qubesbuilder.plugins.source import SourcePlugin, SourceError

log = get_logger("source_rpm")


class RPMSourcePlugin(SourcePlugin):
    """
    Manage RPM distribution source.

    Stages:
        - prep: Prepare and generate source RPM.
    """

    plugin_dependencies = ["source"]

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool = False,
        debug: bool = False,
        skip_if_exists: bool = False,
    ):
        super().__init__(
            component=component,
            dist=dist,
            executor=executor,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
            skip_if_exists=skip_if_exists,
        )

        # Add some environment variables needed to render mock root configuration
        # FIXME: Review legacy usage of "dom0" in components.
        #  "host" is aliased as "dom0" for legacy reason (it also applies in "build_rpm" plugin).
        self.environment.update(
            {
                "DIST": self.dist.name,
                "PACKAGE_SET": self.dist.package_set.replace("host", "dom0"),
            }
        )

    def update_parameters(self):
        """
        Update plugin parameters based on component .qubesbuilder.
        """
        super().update_parameters()

        # Per distribution (e.g. host-fc42) overrides per package set (e.g. host)
        parameters = self.component.get_parameters(self._placeholders)
        self.parameters.update(parameters.get(self.dist.package_set, {}).get("rpm", {}))
        self.parameters.update(
            parameters.get(self.dist.distribution, {}).get("rpm", {})
        )

    def run(self, stage: str):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage == "prep":
            # Update parameters
            self.update_parameters()

            # Check if we have RPM related content defined
            if not self.parameters.get("spec", []):
                log.info(f"{self.component}:{self.dist}: Nothing to be done.")
                return

            distfiles_dir = self.get_distfiles_dir()
            artifacts_dir = self.get_dist_component_artifacts_dir(stage)

            # Compare previous artifacts hash with current source hash
            if all(
                self.get_source_hash()
                == self.get_artifacts_info(
                    stage, os.path.basename(spec).replace(".spec", "")
                ).get("source-hash", None)
                for spec in self.parameters["spec"]
            ):
                log.info(
                    f"{self.component}:{self.dist}: Source hash is the same than already prepared source. Skipping."
                )
                return

            # Clean previous build artifacts
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir.as_posix())
            artifacts_dir.mkdir(parents=True)

            for spec in self.parameters["spec"]:
                # Source component directory inside executors
                source_dir = BUILDER_DIR / self.component.name

                # spec file basename will be used as prefix for some artifacts
                spec_bn = os.path.basename(spec).replace(".spec", "")

                # Generate %{name}-%{version}-%{release} and %Source0
                copy_in = [
                    (self.component.source_dir, BUILDER_DIR),
                    (self.plugins_dir / "source_rpm", PLUGINS_DIR),
                ] + [
                    (self.plugins_dir / dependency, PLUGINS_DIR)
                    for dependency in self.plugin_dependencies
                ]

                copy_out = [
                    (source_dir / f"{spec_bn}_package_release_name", artifacts_dir),
                    (source_dir / f"{spec_bn}_packages.list", artifacts_dir),
                ]
                cmd = [
                    f"{PLUGINS_DIR}/source_rpm/scripts/get-source-info "
                    f"{source_dir} {source_dir / spec} {self.dist.tag}"
                ]
                try:
                    self.executor.run(
                        cmd, copy_in, copy_out, environment=self.environment
                    )
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to get source information: {str(e)}."
                    raise SourceError(msg) from e

                # Read package release name
                with open(artifacts_dir / f"{spec_bn}_package_release_name") as f:
                    data = f.read().splitlines()
                if len(data) < 2:
                    msg = f"{self.component}:{self.dist}:{spec}: Invalid data."
                    raise SourceError(msg)

                source_rpm = f"{data[0]}.src.rpm"
                # Source0 may contain a URL
                source_orig = os.path.basename(data[1])
                if not is_filename_valid(source_rpm) and not is_filename_valid(
                    source_orig
                ):
                    msg = f"{self.component}:{self.dist}:{spec}: Invalid source names."
                    raise SourceError(msg)

                # Read packages list
                packages_list = []
                with open(artifacts_dir / f"{spec_bn}_packages.list") as f:
                    data = f.read().splitlines()
                for line in data:
                    if not is_filename_valid(line):
                        msg = f"{self.component}:{self.dist}:{spec}: Invalid package name."
                        raise SourceError(msg)
                    packages_list.append(line)

                #
                # Create source RPM
                #

                # Copy-in distfiles, content and source
                copy_in = [
                    (distfiles_dir, BUILDER_DIR),
                    (self.component.source_dir, BUILDER_DIR),
                    (self.plugins_dir / "source_rpm", PLUGINS_DIR),
                ] + [
                    (self.plugins_dir / dependency, PLUGINS_DIR)
                    for dependency in self.plugin_dependencies
                ]

                # Copy-out source RPM
                copy_out = [
                    (BUILD_DIR / source_rpm, artifacts_dir),
                ]

                cmd = []
                # Create archive if no external file is provided.
                if not self.parameters.get("files", []):
                    cmd += [
                        f"{PLUGINS_DIR}/source/scripts/create-archive {source_dir} {source_orig}",
                    ]
                else:
                    for file in self.parameters["files"]:
                        fn = os.path.basename(file["url"])
                        cmd.append(f"mv {DISTFILES_DIR}/{fn} {source_dir}")

                # Generate the spec that Mock will use for creating source RPM ensure 'mock'
                # group can access build directory
                cmd += [
                    f"{PLUGINS_DIR}/source_rpm/scripts/generate-spec {source_dir} {source_dir / spec}.in {source_dir / spec}",
                    f"mkdir -p {BUILD_DIR}",
                    f"sudo chown -R user:mock {BUILD_DIR}",
                ]
                # Run 'mock' to generate source RPM
                mock_conf = f"{self.dist.fullname}-{self.dist.version}-{self.dist.architecture}.cfg"
                mock_cmd = [
                    f"sudo --preserve-env=DIST,PACKAGE_SET,USE_QUBES_REPO_VERSION",
                    f"/usr/libexec/mock/mock",
                    "--buildsrpm",
                    f"--spec {source_dir / spec}",
                    f"--root /builder/plugins/source_rpm/mock/{mock_conf}",
                    f"--sources={source_dir}",
                    f"--resultdir={BUILD_DIR}",
                    "--disablerepo=builder-local",
                ]
                if self.verbose:
                    mock_cmd.append("--verbose")

                cmd += [" ".join(mock_cmd)]
                try:
                    self.executor.run(
                        cmd, copy_in, copy_out, environment=self.environment
                    )
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to generate SRPM: {str(e)}."
                    raise SourceError(msg) from e

                # Save package information we parsed for next stages
                try:
                    info = {
                        "srpm": source_rpm,
                        "rpms": packages_list,
                        "source-hash": self.get_source_hash(),
                    }
                    self.save_artifacts_info(stage=stage, basename=spec_bn, info=info)

                    # Clean previous text files as all info are stored inside source_info
                    os.remove(artifacts_dir / f"{spec_bn}_package_release_name")
                    os.remove(artifacts_dir / f"{spec_bn}_packages.list")
                except OSError as e:
                    msg = f"{self.component}:{self.dist}:{spec}: Failed to clean artifacts: {str(e)}."
                    raise SourceError(msg) from e
