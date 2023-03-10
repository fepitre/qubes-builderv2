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

import os.path
import re
import shutil
from pathlib import Path
from typing import List

from qubesbuilder.component import QubesComponent
from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import ExecutorError
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import ArchlinuxDistributionPlugin
from qubesbuilder.plugins.build import BuildPlugin, BuildError

log = get_logger("build_archlinux")


def clean_local_repository(
    repository_dir: Path,
    component: QubesComponent,
    dist: QubesDistribution,
    all_versions: bool = False,
):
    """
    Remove package from local repository.
    """
    log.info(
        f"{component}:{dist}: Cleaning local repository '{repository_dir}'"
        f"{' (all versions)' if all_versions else ''}."
    )
    if all_versions:
        for version_dir in repository_dir.glob(f"{component.name}_*"):
            shutil.rmtree(version_dir.as_posix())
    else:
        target_dir = repository_dir / f"{component.name}_{component.version}"
        if target_dir.exists():
            shutil.rmtree(target_dir.as_posix())


def provision_local_repository(
    build: str,
    repository_dir: Path,
    component: QubesComponent,
    dist: QubesDistribution,
    source_info: dict,
    packages_list: List,
    prep_artifacts_dir: Path,
    build_artifacts_dir: Path,
):
    """
    Provision local builder repository.
    """
    log.info(
        f"{component}:{dist}:{build}: Provisioning local repository '{repository_dir}'."
    )

    # Create target directory that will have hardlinks to PKGs
    target_dir = repository_dir / f"{component.name}_{component.version}"
    target_dir.mkdir(parents=True, exist_ok=True)

    try:
        # pkgs
        for pkg in packages_list:
            pkg_path = build_artifacts_dir / "pkgs" / pkg
            target_path = target_dir / pkg
            os.link(pkg_path, target_path)
    except (ValueError, PermissionError, NotImplementedError, FileExistsError) as e:
        msg = f"{component}:{dist}:{build}: Failed to provision local repository."
        raise BuildError(msg) from e


class ArchlinuxBuildPlugin(ArchlinuxDistributionPlugin, BuildPlugin):
    """
    ArchlinuxBuildPlugin manages Archlinux distribution build.

    Stages:
        - build - Build ArchLinux packages and provision local repository.

    Entry points:
        - build
    """

    stages = ["build"]
    dependencies = ["build"]

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        config: Config,
        manager: PluginManager,
        **kwargs,
    ):
        super().__init__(component=component, dist=dist, config=config, manager=manager)

        # Add some environment variables needed to render mock root configuration
        self.environment.update(
            {"DIST": self.dist.name, "PACKAGE_SET": self.dist.package_set}
        )
        if self.config.use_qubes_repo:
            self.environment.update(
                {
                    "USE_QUBES_REPO_VERSION": str(
                        self.config.use_qubes_repo.get("version", None)
                    ),
                    "USE_QUBES_REPO_TESTING": "1"
                    if self.config.use_qubes_repo.get("testing", None)
                    else "0",
                }
            )

    def update_parameters(self, stage: str):
        super().update_parameters(stage)

        # Set and update parameters based on top-level "source",
        # per package set and per distribution.
        parameters = self.component.get_parameters(self.get_placeholders(stage))

        self._parameters.update(parameters.get("source", {}))
        self._parameters.update(
            parameters.get(self.dist.package_set, {}).get("source", {})
        )
        self._parameters.update(
            parameters.get(self.dist.distribution, {}).get("source", {})
        )

    def run(self, stage: str):
        """
        Run plugin for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage != "build" or not self.has_component_packages("build"):
            return

        executor = self.config.get_executor_from_config(stage)
        parameters = self.get_parameters(stage)

        artifacts_dir = self.get_dist_component_artifacts_dir(stage)
        distfiles_dir = self.get_component_distfiles_dir()
        source_dir = source_dir = executor.get_builder_dir() / self.component.name
        pkgs_dir = artifacts_dir / "pkgs"

        # Compare previous artifacts hash with current source hash
        if all(
            self.component.get_source_hash()
            == self.get_dist_artifacts_info(stage, build.mangle()).get(
                "source-hash", None
            )
            for build in parameters["build"]
        ):
            log.info(
                f"{self.component}:{self.dist}: Source hash is the same than already built source. Skipping."
            )
            return

        # Clean previous build artifacts
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir.as_posix())
        artifacts_dir.mkdir(parents=True)

        # Create PKGs folder
        pkgs_dir.mkdir(parents=True)

        # Source artifacts
        prep_artifacts_dir = self.get_dist_component_artifacts_dir(stage="prep")

        # Local build repository
        repository_dir = self.get_repository_dir() / self.dist.distribution
        repository_dir.mkdir(parents=True, exist_ok=True)

        # Remove previous versions in order to keep the latest one only
        clean_local_repository(repository_dir, self.component, self.dist, True)

        for build in parameters["build"]:
            # spec file basename will be used as prefix for some artifacts
            build_bn = build.mangle()

            # Read information from source stage
            source_info = self.get_dist_artifacts_info(stage="prep", basename=build_bn)

            if not source_info.get("pkgs", None):
                raise BuildError(
                    f"Cannot find PKGs for '{build}'. Missing 'prep' stage call?"
                )

            # Copy-in source
            copy_in = [
                (self.component.source_dir, executor.get_builder_dir()),
                (distfiles_dir, executor.get_distfiles_dir()),
                (repository_dir, executor.get_repository_dir()),
                (
                    self.manager.entities["build_archlinux"].directory,
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
                (executor.get_builder_dir() / source_dir / pkg, pkgs_dir)
                for pkg in source_info["pkgs"]
            ]

            # # Createrepo of local builder repository and ensure 'mock' group can access
            # # build directory
            # cmd = [
            #     f"cd {executor.get_repository_dir()}",
            #     "createrepo_c .",
            #     f"sudo chown -R {executor.get_user()}:mock {executor.get_build_dir()}",
            # ]

            cmd = [
                f"{executor.get_plugins_dir()}/build_archlinux/scripts/generate-pkgbuild {source_dir} {source_dir}/{build}/PKGBUILD.in {source_dir}/PKGBUILD",
                "sudo pacman-key --init",
                "sudo pacman-key --populate"
            ]

            for file in parameters.get("files", []):
                fn = os.path.basename(file["url"])
                if file.get("uncompress", False):
                    fn = Path(fn).with_suffix("").name
                cmd.append(
                    f"mv {executor.get_distfiles_dir() / self.component.name / fn} {source_dir}"
                )
                if file.get("signature", None):
                    cmd.append(
                        f"mv {executor.get_distfiles_dir() / self.component.name / os.path.basename(file['signature'])} {source_dir}"
                    )

            chroot_dir = self.get_cache_dir() / "chroot" / self.dist.name
            chroot_archive = "root.tar.gz"
            if (chroot_dir / chroot_archive).exists():
                copy_in += [(chroot_dir / chroot_archive, executor.get_cache_dir())]
                cmd += [
                    f"sudo mkdir -p {executor.get_cache_dir()}/extra-x86_64",
                    f"cd {executor.get_cache_dir()}/extra-x86_64",
                    f"sudo tar xvf {executor.get_cache_dir() / chroot_archive}",
                ]

            # if self.config.increment_devel_versions:
            #     dist_tag = f"{self.component.devel}.{self.dist.tag}"
            # else:
            #     dist_tag = self.dist.tag

            cmd += [
                f"cd {source_dir}",
                f"sudo extra-x86_64-build -r {executor.get_cache_dir()} -- -- --syncdeps --noconfirm --skipinteg",
            ]

            try:
                executor.run(cmd, copy_in, copy_out, environment=self.environment)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}:{build}: Failed to build PKGs: {str(e)}."
                raise BuildError(msg) from e

            # Get packages list that have been actually built from predicted ones
            packages_list = []
            for pkg in source_info["pkgs"]:
                if os.path.exists(pkgs_dir / pkg):
                    packages_list.append(pkg)

            info = source_info
            info.update(
                    {
                        "pkgs": packages_list,
                        "source-hash": self.component.get_source_hash(),
                    }
                )

            # Provision builder local repository
            provision_local_repository(
                build=build,
                component=self.component,
                dist=self.dist,
                repository_dir=repository_dir,
                source_info=info,
                packages_list=packages_list,
                prep_artifacts_dir=prep_artifacts_dir,
                build_artifacts_dir=artifacts_dir,
            )

            # Save package information we parsed for next stages
            self.save_dist_artifacts_info(stage=stage, basename=build_bn, info=info)


PLUGINS = [ArchlinuxBuildPlugin]
