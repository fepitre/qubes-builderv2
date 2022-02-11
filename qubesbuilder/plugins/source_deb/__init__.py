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

from qubesbuilder.common import is_filename_valid
from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import BUILDER_DIR, PLUGINS_DIR, BUILD_DIR, DISTFILES_DIR
from qubesbuilder.plugins.source import SourcePlugin, SourceError

log = get_logger("source_deb")


class DEBSourcePlugin(SourcePlugin):
    """
    Manage Debian distribution source.

    Stages:
        - prep: Prepare and generate Debian source package (.orig.tar.*, .dsc and .debian.tar.xz).
    """

    plugin_dependencies = ["source"]

    def __init__(self, component: QubesComponent, dist: QubesDistribution, executor: Executor, plugins_dir: Path,
                 artifacts_dir: Path, verbose: bool = False, debug: bool = False,
                 skip_if_exists: bool = False):
        super().__init__(component=component, dist=dist, executor=executor, plugins_dir=plugins_dir,
                         artifacts_dir=artifacts_dir, verbose=verbose, debug=debug,
                         skip_if_exists=skip_if_exists)

        self.environment = {
            "DIST": self.dist.name
        }
        if self.verbose:
            self.environment["VERBOSE"] = 1
        if self.debug:
            self.environment["DEBUG"] = 1

    def update_parameters(self):
        """
        Update plugin parameters based on component .qubesbuilder.
        """
        super().update_parameters()

        # Per distribution (e.g. vm-bookworm) overrides per package set (e.g. vm)
        parameters = self.component.get_parameters(self._placeholders)
        self.parameters.update(parameters.get(self.dist.package_set, {}).get("deb", {}))
        self.parameters.update(parameters.get(self.dist.distribution, {}).get("deb", {}))

    def run(self, stage: str):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage == "prep":
            # Update parameters
            self.update_parameters()

            # Check if we have Debian related content defined
            if not self.parameters.get("build", None):
                log.info(f"{self.component}: nothing to be done for {self.dist}")
                return

            distfiles_dir = self.get_distfiles_dir()
            artifacts_dir = self.get_component_dir(stage)
            artifacts_dir.mkdir(parents=True, exist_ok=True)

            for directory in self.parameters["build"]:
                # Source component directory inside executors
                source_dir = BUILDER_DIR / self.component.name

                # Generate package release name
                copy_in = [
                    (self.component.source_dir, BUILDER_DIR / self.component.name),
                    (self.plugins_dir / "source_deb", PLUGINS_DIR),
                ]
                for dependency in self.plugin_dependencies:
                    copy_in += [(self.plugins_dir / dependency, PLUGINS_DIR)]

                copy_out = [
                    (source_dir / f"{directory}_package_release_name", artifacts_dir)
                ]

                # Update changelog
                bash_cmd = [
                    f"{PLUGINS_DIR}/source_deb/scripts/modify-changelog-for-build "
                    f"{source_dir} {directory} {self.dist.name} {self.dist.tag}",
                ]

                bash_cmd += [
                    f"{PLUGINS_DIR}/source_deb/scripts/get-source-info {source_dir} {directory}"
                ]

                env = self.environment
                env.update({"LC_ALL": "C", "DEBFULLNAME": "Builder", "DEBEMAIL": "user@localhost"})

                cmd = ["/bin/bash", "-c", " && ".join(bash_cmd)]
                try:
                    self.executor.run(cmd, copy_in, copy_out, environment=env)
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: " \
                          f"Failed to get source information."
                    raise SourceError(msg) from e

                # Read package release name
                with open(artifacts_dir / f"{directory}_package_release_name") as f:
                    data = f.read().splitlines()
                if len(data) != 2:
                    msg = f"{self.component}:{self.dist}:{directory}: Invalid data."
                    raise SourceError(msg)

                package_release_name = data[0]
                package_release_name_full = data[1]
                if not is_filename_valid(package_release_name) and \
                        not is_filename_valid(package_release_name_full):
                    msg = f"{self.component}:{self.dist}:{directory}: Invalid source names."
                    raise SourceError(msg)

                source_dsc = f"{package_release_name_full}.dsc"
                source_debian = f"{package_release_name_full}.debian.tar.xz"
                if self.parameters.get("files", []):
                    # FIXME: The first file is the source archive. Is it valid for all the cases?
                    ext = self.parameters["files"][0]["url"].split(".")[-1]
                    msg = f"{self.component}:{self.dist}:{directory}: Invalid extension '{ext}'."
                    if ext not in ("gz", "bz2", "gz", "lzma2"):
                        raise SourceError(msg)
                else:
                    ext = "gz"
                source_orig = f"{package_release_name}.orig.tar.{ext}"

                #
                # Create Debian source: orig, debian and dsc
                #

                # Copy-in distfiles, dependencies, source and Debian directory
                copy_in = [
                    (self.component.source_dir, BUILDER_DIR / self.component.name),
                    (self.plugins_dir / "source_deb", PLUGINS_DIR),
                    (distfiles_dir, BUILDER_DIR)
                ]
                for dependency in self.plugin_dependencies:
                    copy_in += [(self.plugins_dir / dependency, PLUGINS_DIR)]

                # Copy-out Debian source package (.orig.tar.*, .dsc and .debian.tar.xz)
                copy_out = [
                    (BUILDER_DIR / source_orig, artifacts_dir),
                    (BUILDER_DIR / source_debian, artifacts_dir),
                    (BUILDER_DIR / source_dsc, artifacts_dir),
                    (BUILDER_DIR / f"{directory}_packages.list", artifacts_dir)
                ]

                # Init command with .qubesbuilder command entries
                bash_cmd = self.parameters.get("source", {}).get("commands", [])

                # Update changelog
                bash_cmd += [
                    f"{PLUGINS_DIR}/source_deb/scripts/modify-changelog-for-build "
                    f"{source_dir} {directory} {self.dist.name} {self.dist.tag}",
                ]

                # Create archive if no external file is provided.
                if not self.parameters.get("files", []):
                    bash_cmd += [
                        f"{PLUGINS_DIR}/source/scripts/create-archive {source_dir} {source_orig}",
                        f"mv {source_dir}/{source_orig} {BUILDER_DIR}"
                    ]
                else:
                    for file in self.parameters["files"]:
                        fn = os.path.basename(file["url"])
                        bash_cmd.append(f"mv {DISTFILES_DIR}/{fn} {BUILDER_DIR}/{source_orig}")

                gen_packages_list_cmd = [
                    f"{PLUGINS_DIR}/source_deb/scripts/debian-get-packages-list",
                    str(BUILDER_DIR / source_dsc), self.dist.version,
                    f">{BUILDER_DIR}/{directory}_packages.list"
                ]

                # Run 'dpkg-source' inside build directory
                bash_cmd += [
                    f"cd {BUILD_DIR}", f"cp -r {source_dir / directory} .",
                    "dpkg-source -b .", " ".join(gen_packages_list_cmd)
                ]

                cmd = ["/bin/bash", "-c", " && ".join(bash_cmd)]
                try:
                    self.executor.run(cmd, copy_in, copy_out)
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to generate source."
                    raise SourceError(msg) from e

                # Read packages list
                packages_list = []
                with open(artifacts_dir / f"{directory}_packages.list") as f:
                    data = f.read().splitlines()
                for line in data:
                    if not is_filename_valid(line):
                        msg = f"{self.component}:{self.dist}:{directory}: Invalid package name."
                        raise SourceError(msg)
                    packages_list.append(line)

                # Save package information we parsed for next stages
                try:
                    with open(artifacts_dir / f"{directory}_source_info.yml", "w") as f:
                        info = {
                            "package-release-name": package_release_name,
                            "package-release-name-full": package_release_name_full,
                            "orig": source_orig,
                            "dsc": source_dsc,
                            "debian": source_debian,
                            "packages": packages_list,
                        }
                        f.write(yaml.safe_dump(info))

                    # Clean previous text files as all info are stored inside source_info
                    os.remove(artifacts_dir / f'{directory}_package_release_name')
                    os.remove(artifacts_dir / f'{directory}_packages.list')
                except (PermissionError, yaml.YAMLError) as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to write source info."
                    raise SourceError(msg) from e
                except OSError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to clean artifacts."
                    raise SourceError(msg) from e
