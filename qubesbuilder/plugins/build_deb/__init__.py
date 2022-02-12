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
from pathlib import Path
from typing import List

import yaml

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import BUILDER_DIR, BUILD_DIR, PLUGINS_DIR, REPOSITORY_DIR
from qubesbuilder.plugins.build import BuildPlugin, BuildError

log = get_logger("build_deb")


def provision_local_repository(
    debian_directory: str,
    repository_dir: Path,
    component: QubesComponent,
    dist: QubesDistribution,
    source_info: dict,
    packages_list: List,
    build_artifacts_dir: Path,
):
    """
    Provision local builder repository.
    """
    log.info(
        f"{component}:{dist}:{debian_directory}: Provisioning local repository '{repository_dir}'."
    )

    # Create target directory that will have hardlinks to built packages
    target_dir = repository_dir / f"{component.name}-{component.version}"
    if target_dir.exists():
        shutil.rmtree(target_dir.as_posix())
    target_dir.mkdir(parents=True)

    try:
        # deb
        files = [build_artifacts_dir / deb for deb in packages_list]
        files += [
            build_artifacts_dir / source_info[f] for f in ("orig", "dsc", "debian")
        ]

        # changes and buildinfo
        files += [
            build_artifacts_dir / source_info["changes"],
            build_artifacts_dir / source_info["buildinfo"],
        ]

        # create hardlinks
        for f in files:
            target_path = target_dir / f.name
            # target_path.hardlink_to(f)
            os.link(f, target_path)
    except (ValueError, PermissionError, NotImplementedError) as e:
        msg = f"{component}:{dist}:{debian_directory}: Failed to create repository."
        raise BuildError(msg) from e


class DEBBuildPlugin(BuildPlugin):
    """
    Manage Debian distribution build.
    """

    plugin_dependencies = ["source_deb", "build"]

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool = False,
        debug: bool = False,
        use_qubes_repo: dict = None,
    ):
        super().__init__(
            component=component,
            dist=dist,
            executor=executor,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
            use_qubes_repo=use_qubes_repo,
        )

    def update_parameters(self):
        """
        Update plugin parameters based on component .qubesbuilder.
        """
        super().update_parameters()

        # Per distribution (e.g. vm-bookworm) overrides per package set (e.g. vm)
        parameters = self.component.get_parameters(self._placeholders)
        self.parameters.update(parameters.get(self.dist.package_set, {}).get("deb", {}))
        self.parameters.update(
            parameters.get(self.dist.distribution, {}).get("deb", {})
        )

    def run(self, stage: str):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage == "build":
            # Update parameters
            self.update_parameters()

            # Check if we have Debian related content defined
            if not self.parameters.get("build", None):
                log.info(f"{self.component}: nothing to be done for {self.dist}")
                return

            artifacts_dir = self.get_component_dir(stage)

            # Clean previous build artifacts
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir.as_posix())
            artifacts_dir.mkdir(parents=True)

            # Source artifacts
            prep_artifacts_dir = self.get_component_dir(stage="prep")

            repository_dir = self.get_repository_dir() / self.dist.distribution
            repository_dir.mkdir(parents=True, exist_ok=True)

            # Remove previous versions in order to keep latest one only
            for build in repository_dir.glob(f"{self.component.name}-*"):
                shutil.rmtree(build.as_posix())

            for directory in self.parameters["build"]:
                # Read information from source stage
                try:
                    with open(prep_artifacts_dir / f"{directory}_source_info.yml") as f:
                        source_info = yaml.safe_load(f.read())
                except (FileNotFoundError, PermissionError) as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to read source info."
                    raise BuildError(msg) from e

                #
                # Build Debian packages
                #

                # Copy-in plugin, repository and sources
                copy_in = [
                    (self.plugins_dir / "build_deb", PLUGINS_DIR),
                    (self.plugins_dir / "build_deb" / "pbuilder", BUILDER_DIR),
                    (repository_dir, REPOSITORY_DIR),
                    (prep_artifacts_dir / source_info["dsc"], BUILD_DIR),
                    (prep_artifacts_dir / source_info["orig"], BUILD_DIR),
                    (prep_artifacts_dir / source_info["debian"], BUILD_DIR),
                ]
                # Copy-in plugin dependencies
                copy_in += [
                    (self.plugins_dir / plugin, PLUGINS_DIR)
                    for plugin in self.plugin_dependencies
                ]

                results_dir = BUILDER_DIR / "pbuilder" / "results"
                source_info["changes"] = source_info["dsc"].replace(
                    ".dsc", "_amd64.changes"
                )
                source_info["buildinfo"] = source_info["dsc"].replace(
                    ".dsc", "_amd64.buildinfo"
                )
                copy_out = [
                    (
                        results_dir
                        / source_info["dsc"].replace(".dsc", "_amd64.changes"),
                        artifacts_dir,
                    ),
                    (
                        results_dir
                        / source_info["dsc"].replace(".dsc", "_amd64.buildinfo"),
                        artifacts_dir,
                    ),
                ]
                copy_out += [
                    (results_dir / deb, artifacts_dir)
                    for deb in source_info["packages"]
                ]

                # Create local builder repository
                extra_sources = (
                    f"deb [trusted=yes] file:///tmp/qubes-deb {self.dist.name} main"
                )
                # extra_sources = ""
                cmd = [
                    f"{PLUGINS_DIR}/build_deb/scripts/create-local-repo {REPOSITORY_DIR} {self.dist.fullname} {self.dist.name}"
                ]

                if self.use_qubes_repo.get("version", None):
                    qubes_version = self.use_qubes_repo["version"]
                    extra_sources = f"{extra_sources}|deb [arch=amd64] http://deb.qubes-os.org/r{qubes_version}/vm {self.dist.name} main"
                    cmd += [
                        f"gpg --dearmor "
                        f"< {PLUGINS_DIR}/build_deb/keys/qubes-debian-r{qubes_version}.asc "
                        f"> {BUILDER_DIR}/pbuilder/qubes-keyring.gpg"
                    ]
                    if self.use_qubes_repo.get("testing", False):
                        extra_sources = f"{extra_sources}|deb [arch=amd64] http://deb.qubes-os.org/r{qubes_version}/vm {self.dist.name}-testing main"

                # FIXME: allow to pass a prebuilt pbuilder base.tgz
                cmd += [
                    f"sudo -E pbuilder create "
                    f"--distribution {self.dist.name} "
                    f"--configfile {BUILDER_DIR}/pbuilder/pbuilderrc "
                    f"--othermirror \"{extra_sources}\""
                ]

                cmd += [
                    f"sudo -E pbuilder build --override-config "
                    f"--distribution {self.dist.name} "
                    f"--configfile {BUILDER_DIR}/pbuilder/pbuilderrc "
                    f"--othermirror \"{extra_sources}\" "
                    f"{str(BUILD_DIR / source_info['dsc'])}"
                ]
                try:
                    self.executor.run(
                        cmd,
                        copy_in,
                        copy_out,
                        environment=self.environment,
                        no_fail_copy_out=True,
                    )
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to build packages."
                    raise BuildError(msg) from e

                # Get packages list that have been actually built from predicted ones
                packages_list = []
                for deb in source_info["packages"]:
                    if os.path.exists(artifacts_dir / deb):
                        packages_list.append(deb)

                # We prefer to keep originally copied in source to cross check
                # what's inside the resulting .changes file.
                files = [
                    prep_artifacts_dir / source_info[f]
                    for f in ("orig", "dsc", "debian")
                ]
                for file in files:
                    target_path = artifacts_dir / file.name
                    shutil.copy2(file, target_path)

                # Provision builder local repository
                provision_local_repository(
                    debian_directory=directory,
                    component=self.component,
                    dist=self.dist,
                    repository_dir=repository_dir,
                    source_info=source_info,
                    packages_list=packages_list,
                    build_artifacts_dir=artifacts_dir,
                )

                # Save package information we parsed for next stages
                try:
                    with open(artifacts_dir / f"{directory}_build_info.yml", "w") as f:
                        info = source_info
                        info["packages"] = packages_list
                        f.write(yaml.safe_dump(info))
                except (PermissionError, yaml.YAMLError) as e:
                    msg = f"{self.component}:{self.dist}:{directory}: Failed to write build info."
                    raise BuildError(msg) from e
