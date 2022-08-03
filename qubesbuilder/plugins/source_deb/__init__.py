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
import tempfile
from pathlib import Path

from qubesbuilder.common import is_filename_valid
from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import (
    BUILDER_DIR,
    PLUGINS_DIR,
    BUILD_DIR,
    DISTFILES_DIR,
)
from qubesbuilder.plugins.source import SourcePlugin, SourceError

log = get_logger("source_deb")


class DEBSourcePlugin(SourcePlugin):
    """
    Manage Debian distribution source.

    Stages:
        - prep: Prepare and generate Debian source package (.orig.tar.*, .dsc and .debian.tar.xz).
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

        self.environment.update(
            {
                "DIST": self.dist.name,
                "LC_ALL": "C",
                "DEBFULLNAME": "Builder",
                "DEBEMAIL": "user@localhost",
            }
        )

    def run(self, stage: str):
        """
        Run plugin for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage == "prep":
            # Check if we have Debian related content defined
            if not self.parameters.get("build", None):
                log.info(f"{self.component}: nothing to be done for {self.dist}")
                return

            distfiles_dir = self.get_component_distfiles_dir()
            artifacts_dir = self.get_dist_component_artifacts_dir(stage)

            # Compare previous artifacts hash with current source hash
            if all(
                self.component.get_source_hash()
                == self.get_dist_artifacts_info(
                    stage=stage, basename=directory.mangle()
                ).get("source-hash", None)
                for directory in self.parameters["build"]
            ):
                log.info(
                    f"{self.component}:{self.dist}: Source hash is the same than already prepared source. Skipping."
                )
                return

            # Clean previous build artifacts
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir.as_posix())
            artifacts_dir.mkdir(parents=True)

            # Get fetch info
            fetch_info = self.get_dist_artifacts_info(
                "fetch",
                "source",
                artifacts_dir=self.get_component_artifacts_dir("fetch"),
            )

            for directory in self.parameters["build"]:
                # Temporary dir for temporary copied-out files
                temp_dir = Path(tempfile.mkdtemp())

                # Source component directory inside executors
                source_dir = BUILDER_DIR / self.component.name

                # directory basename will be used as prefix for some artifacts
                directory_bn = directory.mangle()

                # Generate package release name
                copy_in = [
                    (self.component.source_dir, BUILDER_DIR),
                    (self.plugins_dir / "source_deb", PLUGINS_DIR),
                ]
                for dependency in self.plugin_dependencies:
                    copy_in += [(self.plugins_dir / dependency, PLUGINS_DIR)]

                copy_out = [
                    (source_dir / f"{directory_bn}_package_release_name", temp_dir)
                ]

                # Update changelog
                cmd = [
                    f"{PLUGINS_DIR}/source_deb/scripts/modify-changelog-for-build "
                    f"{source_dir} {directory} {self.dist.name} {self.dist.tag}",
                ]

                cmd += [
                    f"{PLUGINS_DIR}/source_deb/scripts/get-source-info {source_dir} {directory}"
                ]
                try:
                    self.executor.run(
                        cmd, copy_in, copy_out, environment=self.environment
                    )
                except ExecutorError as e:
                    msg = (
                        f"{self.component}:{self.dist}:{directory}: "
                        f"Failed to get source information: {str(e)}."
                    )
                    raise SourceError(msg) from e

                # Read package release name
                with open(temp_dir / f"{directory_bn}_package_release_name") as f:
                    data = f.read().splitlines()
                if len(data) != 3:
                    msg = f"{self.component}:{self.dist}:{directory}: Invalid data."
                    raise SourceError(msg)

                package_release_name = data[0]
                package_release_name_full = data[1]
                package_type = data[2]
                if not is_filename_valid(package_release_name) or not is_filename_valid(
                    package_release_name_full
                ):
                    msg = f"{self.component}:{self.dist}:{directory}: Invalid source names."
                    raise SourceError(msg)

                if package_type not in ("native", "quilt"):
                    msg = f"{self.component}:{self.dist}:{directory}: Invalid source type."
                    raise SourceError(msg)

                source_dsc = f"{package_release_name_full}.dsc"
                if package_type == "native":
                    source_debian = f"{package_release_name_full}.tar.xz"
                else:
                    source_debian = f"{package_release_name_full}.debian.tar.xz"
                if self.parameters.get("files", []):
                    # FIXME: The first file is the source archive. Is it valid for all the cases?
                    ext = self.parameters["files"][0]["url"].split(".")[-1]
                    msg = f"{self.component}:{self.dist}:{directory}: Invalid extension '{ext}'."
                    if ext not in ("gz", "bz2", "xz", "lzma2"):
                        raise SourceError(msg)
                else:
                    ext = "gz"
                source_orig = f"{package_release_name}.orig.tar.{ext}"

                #
                # Create Debian source: orig, debian and dsc
                #

                # Copy-in distfiles, dependencies, source and Debian directory
                copy_in = [
                    (self.component.source_dir, BUILDER_DIR),
                    (self.plugins_dir / "source_deb", PLUGINS_DIR),
                    (distfiles_dir, DISTFILES_DIR),
                ]
                for dependency in self.plugin_dependencies:
                    copy_in += [(self.plugins_dir / dependency, PLUGINS_DIR)]

                # Copy-out Debian source package (.orig.tar.*, .dsc and .debian.tar.xz)
                copy_out = [
                    (BUILDER_DIR / source_dsc, artifacts_dir),
                    (BUILDER_DIR / source_debian, artifacts_dir),
                    (BUILDER_DIR / f"{directory_bn}_packages.list", temp_dir),
                ]
                if package_type == "quilt":
                    copy_out += [(BUILDER_DIR / source_orig, artifacts_dir)]

                # Init command with .qubesbuilder command entries
                cmd = self.parameters.get("source", {}).get("commands", [])

                # Update changelog
                cmd += [
                    f"{PLUGINS_DIR}/source_deb/scripts/modify-changelog-for-build "
                    f"{source_dir} {directory} {self.dist.name} {self.dist.tag}",
                ]

                if package_type == "quilt":
                    # Create archive if no external file is provided.
                    if not self.parameters.get("files", []):
                        cmd += [
                            f"{PLUGINS_DIR}/fetch/scripts/create-archive {source_dir} {source_orig}",
                            f"mv {source_dir}/{source_orig} {BUILDER_DIR}",
                        ]
                    else:
                        for file in self.parameters["files"]:
                            fn = os.path.basename(file["url"])
                            cmd.append(
                                f"mv {DISTFILES_DIR / self.component.name / fn} {BUILDER_DIR}/{source_orig}"
                            )

                gen_packages_list_cmd = [
                    f"{PLUGINS_DIR}/source_deb/scripts/debian-get-packages-list",
                    str(BUILDER_DIR / source_dsc),
                    str(self.dist.version),
                    f">{BUILDER_DIR}/{directory_bn}_packages.list",
                ]

                # Run 'dpkg-source' inside build directory
                if package_type == "quilt":
                    cmd += [
                        f"mkdir -p {BUILD_DIR}",
                        f"cd {BUILD_DIR}",
                        f"cp -r {source_dir / directory} .",
                    ]
                else:
                    # For native package, we need to match archive prefix in order
                    # to not have a different one at build stage. For example,
                    # 'build/' vs 'qubes-utils_4.1.16+deb11u1/'
                    build_dir = str(BUILDER_DIR / package_release_name_full).replace(
                        "_", "-"
                    )
                    cmd += [
                        f"mkdir -p {build_dir}",
                        f"cd {build_dir}",
                        f"cp -r {source_dir}/* .",
                    ]
                cmd += [
                    "dpkg-source -b .",
                    " ".join(gen_packages_list_cmd),
                ]
                try:
                    self.executor.run(
                        cmd, copy_in, copy_out, environment=self.environment
                    )
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to generate source: {str(e)}."
                    raise SourceError(msg) from e

                # Read packages list
                packages_list = []
                with open(temp_dir / f"{directory_bn}_packages.list") as f:
                    data = f.read().splitlines()
                for line in data:
                    if not is_filename_valid(line):
                        msg = f"{self.component}:{self.dist}:{directory}: Invalid package name."
                        raise SourceError(msg)
                    packages_list.append(line)

                # Save package information we parsed for next stages
                try:
                    info = fetch_info
                    info.update(
                        {
                            "package-release-name": package_release_name,
                            "package-release-name-full": package_release_name_full,
                            "package-type": package_type,
                            "dsc": source_dsc,
                            "debian": source_debian,
                            "packages": packages_list,
                            "source-hash": self.component.get_source_hash(),
                        }
                    )
                    if package_type == "quilt":
                        info["orig"] = source_orig

                    self.save_dist_artifacts_info(
                        stage=stage, basename=directory_bn, info=info
                    )

                    # Clean temporary directory
                    shutil.rmtree(temp_dir)
                except OSError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to clean artifacts: {str(e)}."
                    raise SourceError(msg) from e
