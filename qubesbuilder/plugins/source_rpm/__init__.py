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
import shutil
import urllib.parse
from pathlib import Path

from qubesbuilder.common import is_filename_valid
from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.executors.qubes import QubesExecutor
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

    plugin_dependencies = ["fetch", "source"]

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
            backend_vmm=backend_vmm,
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

    def run(self, stage: str):
        """
        Run plugin for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage == "prep":
            # Check if we have RPM related content defined
            if not self.parameters.get("build", []):
                log.info(f"{self.component}:{self.dist}: Nothing to be done.")
                return

            # Compare previous artifacts hash with current source hash
            if all(
                self.component.get_source_hash()
                == self.get_dist_artifacts_info(stage, build.with_suffix("").name).get(
                    "source-hash", None
                )
                for build in self.parameters["build"]
            ):
                log.info(
                    f"{self.component}:{self.dist}: Source hash is the same than already prepared source. Skipping."
                )
                return

            artifacts_dir = self.get_dist_component_artifacts_dir(stage)
            distfiles_dir = self.get_distfiles_dir()

            # Get fetch info
            fetch_info = self.get_dist_artifacts_info(
                "fetch",
                "source",
                artifacts_dir=self.get_component_artifacts_dir("fetch"),
            )

            # Clean previous build artifacts
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir.as_posix())
            artifacts_dir.mkdir(parents=True)

            for build in self.parameters["build"]:
                # Source component directory inside executors
                source_dir = BUILDER_DIR / self.component.name

                # spec file basename will be used as prefix for some artifacts
                build_bn = build.with_suffix("").name

                # Generate %{name}-%{version}-%{release} and %Source0
                copy_in = [
                    (self.component.source_dir, BUILDER_DIR),
                    (self.plugins_dir / "source_rpm", PLUGINS_DIR),
                ] + [
                    (self.plugins_dir / dependency, PLUGINS_DIR)
                    for dependency in self.plugin_dependencies
                ]

                copy_out = [
                    (source_dir / f"{build_bn}_package_release_name", artifacts_dir),
                    (source_dir / f"{build_bn}_packages.list", artifacts_dir),
                ]
                cmd = [
                    f"{PLUGINS_DIR}/source_rpm/scripts/get-source-info "
                    f"{source_dir} {source_dir / build} {self.dist.tag}"
                ]
                try:
                    self.executor.run(
                        cmd, copy_in, copy_out, environment=self.environment
                    )
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{build}: Failed to get source information: {str(e)}."
                    raise SourceError(msg) from e

                # Read package release name
                with open(artifacts_dir / f"{build_bn}_package_release_name") as f:
                    data = f.read().splitlines()
                if len(data) < 2:
                    msg = f"{self.component}:{self.dist}:{build}: Invalid data."
                    raise SourceError(msg)

                source_rpm = f"{data[0]}.src.rpm"
                # Source0 may contain a URL.
                source_orig = os.path.basename(data[1])
                if not is_filename_valid(source_rpm) and not is_filename_valid(
                    source_orig
                ):
                    msg = f"{self.component}:{self.dist}:{build}: Invalid source names."
                    raise SourceError(msg)

                # Read packages list
                packages_list = []
                with open(artifacts_dir / f"{build_bn}_packages.list") as f:
                    data = f.read().splitlines()
                for line in data:
                    if not is_filename_valid(line):
                        msg = f"{self.component}:{self.dist}:{build}: Invalid package name."
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
                    # If no Source0 is provided, we expect 'source' from query-spec.
                    if source_orig != "source":
                        cmd += [
                            f"{PLUGINS_DIR}/fetch/scripts/create-archive {source_dir} {source_orig}",
                        ]
                else:
                    for file in self.parameters["files"]:
                        fn = os.path.basename(file["url"])
                        if file.get("uncompress", False):
                            fn = Path(fn).with_suffix("").name
                        cmd.append(f"mv {DISTFILES_DIR}/{fn} {source_dir}")
                        if file.get("signature", None):
                            cmd.append(
                                f"mv {DISTFILES_DIR}/{os.path.basename(file['signature'])} {source_dir}"
                            )

                for module in fetch_info.get("modules", []):
                    cmd.append(f"mv {DISTFILES_DIR}/{module['archive']} {source_dir}")
                    cmd.append(
                        f"sed -i 's/@{module['name']}@/{module['archive']}/g' {source_dir / build}.in"
                    )

                # Generate the spec that Mock will use for creating source RPM ensure 'mock'
                # group can access build directory
                cmd += [
                    f"{PLUGINS_DIR}/source_rpm/scripts/generate-spec {source_dir} {source_dir / build}.in {source_dir / build}",
                    f"mkdir -p {BUILD_DIR}",
                    f"sudo chown -R user:mock {BUILD_DIR}",
                ]
                # Run 'mock' to generate source RPM
                mock_conf = f"{self.dist.fullname}-{self.dist.version}-{self.dist.architecture}.cfg"
                mock_cmd = [
                    f"sudo --preserve-env=DIST,PACKAGE_SET,USE_QUBES_REPO_VERSION",
                    f"/usr/libexec/mock/mock",
                    "--buildsrpm",
                    f"--spec {source_dir / build}",
                    f"--root /builder/plugins/source_rpm/mock/{mock_conf}",
                    f"--sources={source_dir}",
                    f"--resultdir={BUILD_DIR}",
                    "--disablerepo=builder-local",
                ]
                if isinstance(self.executor, QubesExecutor):
                    mock_cmd.append("--isolation=nspawn")
                else:
                    msg = f"{self.component}:{self.dist}:{build}: Mock isolation set to 'simple', build has full network access. Use 'qubes' executor for network-isolated build."
                    log.warning(msg)
                    mock_cmd.append("--isolation=simple")
                if self.verbose:
                    mock_cmd.append("--verbose")

                cmd += [" ".join(mock_cmd)]
                try:
                    self.executor.run(
                        cmd, copy_in, copy_out, environment=self.environment
                    )
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{build}: Failed to generate SRPM: {str(e)}."
                    raise SourceError(msg) from e

                # Save package information we parsed for next stages
                try:
                    info = fetch_info
                    info.update(
                        {
                            "srpm": source_rpm,
                            "rpms": packages_list,
                            "source-hash": self.component.get_source_hash(),
                        }
                    )
                    self.save_dist_artifacts_info(
                        stage=stage, basename=build_bn, info=info
                    )

                    # Clean previous text files as all info are stored inside source_info
                    os.remove(artifacts_dir / f"{build_bn}_package_release_name")
                    os.remove(artifacts_dir / f"{build_bn}_packages.list")
                except OSError as e:
                    msg = f"{self.component}:{self.dist}:{build}: Failed to clean artifacts: {str(e)}."
                    raise SourceError(msg) from e
