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
import shutil
from pathlib import Path
from typing import List

from qubesbuilder.component import QubesComponent
from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import ExecutorError
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.log import get_logger
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.plugins import ArchlinuxDistributionPlugin
from qubesbuilder.plugins.build import BuildPlugin, BuildError
from qubesbuilder.plugins.chroot_archlinux import get_pacman_cmd, get_archchroot_cmd

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
    packages_list: List,
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
    dependencies = ["build", "chroot_archlinux"]

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
                    "USE_QUBES_REPO_TESTING": (
                        "1" if self.config.use_qubes_repo.get("testing", None) else "0"
                    ),
                    # FIXME: Allow to define repo proxy
                    "REPO_PROXY": "",
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

        executor = self.get_executor(stage)
        parameters = self.get_parameters(stage)

        if isinstance(executor, LocalExecutor):
            raise BuildError("This plugin does not yet support local executor.")

        artifacts_dir = self.get_dist_component_artifacts_dir(stage)
        distfiles_dir = self.get_component_distfiles_dir()
        source_dir = executor.get_builder_dir() / self.component.name
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

            if not source_info.get("packages", None):
                raise BuildError(
                    f"Cannot find PKGs for '{build}'. Missing 'prep' stage call?"
                )

            files_inside_executor_with_placeholders = []

            # Copy-in source
            copy_in = [
                (self.component.source_dir, executor.get_builder_dir()),
                (prep_artifacts_dir / "PKGBUILD", source_dir),
                (distfiles_dir, executor.get_distfiles_dir()),
                (repository_dir, executor.get_repository_dir()),
                (
                    self.manager.entities["build_archlinux"].directory,
                    executor.get_plugins_dir(),
                ),
                (
                    self.manager.entities["chroot_archlinux"].directory
                    / "keys/qubes-repo-archlinux-key.asc",
                    executor.get_builder_dir(),
                ),
            ] + [
                (
                    self.manager.entities[dependency].directory,
                    executor.get_plugins_dir(),
                )
                for dependency in self.dependencies
            ]

            if source_info.get("source-archive", None):
                copy_in.append(
                    (prep_artifacts_dir / source_info["source-archive"], source_dir)
                )

            copy_out = [
                (executor.get_builder_dir() / source_dir / pkg, pkgs_dir)
                for pkg in source_info["packages"]
            ]

            # pacman and makepkg configuration files
            pacman_conf_template = (
                f"{executor.get_plugins_dir()}/chroot_archlinux/conf/pacman.conf.j2"
            )

            pacman_conf = "/usr/local/share/devtools/pacman.conf.d/qubes-x86_64.conf"

            makepkg_conf = f"{executor.get_plugins_dir()}/chroot_archlinux/conf/makepkg-x86_64.conf"

            cmd = [
                f"sudo cp {makepkg_conf} /usr/local/share/devtools/makepkg.conf.d/qubes-x86_64.conf",
            ]

            pacman_cmd = get_pacman_cmd(
                gen_path=f"{executor.get_plugins_dir()}/chroot_archlinux/scripts/generate-pacman",
                conf_template=pacman_conf_template,
                conf=pacman_conf,
                servers=self.config.get("mirrors", {}).get(self.dist.name, []),
                use_qubes_repo_version=self.config.use_qubes_repo.get("version", None),
                use_qubes_repo_testing=self.config.use_qubes_repo.get("testing", False),
            )

            chroot_dir = self.get_cache_dir() / "chroot" / self.dist.name
            chroot_archive = "root.tar.gz"

            if (chroot_dir / chroot_archive).exists():
                log.info(
                    f"{self.component}:{self.dist}: Chroot cache exists. Will use it."
                )

                copy_in += [(chroot_dir / chroot_archive, executor.get_cache_dir())]

                cmd += [
                    f"sudo mkdir -p {executor.get_cache_dir()}/qubes-x86_64",
                    f"cd {executor.get_cache_dir()}/qubes-x86_64",
                    f"sudo tar xf {executor.get_cache_dir() / chroot_archive}",
                ] + pacman_cmd

                # Ensure to regenerate pacman keyring
                cmd += [
                    "sudo rm -rf /etc/pacman.d/gnupg/private-keys-v1.d",
                    "sudo pacman-key --init",
                    "sudo pacman-key --populate",
                ]
            else:
                log.info(
                    f"{self.component}:{self.dist}: Chroot cache does not exists. Will create it."
                )
                # We don't need builder-local to create fresh chroot
                cmd += pacman_cmd + get_archchroot_cmd(
                    chroot_dir,
                    pacman_conf,
                    makepkg_conf,
                )

            # Once we generated a normal configuration without builder-local needed
            # we regenerate one with it enabled.
            pacman_cmd = get_pacman_cmd(
                gen_path=f"{executor.get_plugins_dir()}/chroot_archlinux/scripts/generate-pacman",
                conf_template=pacman_conf_template,
                conf=pacman_conf,
                servers=self.config.get("mirrors", {}).get(self.dist.name, []),
                enable_builder_local=True,
                use_qubes_repo_version=self.config.use_qubes_repo.get("version", None),
                use_qubes_repo_testing=self.config.use_qubes_repo.get("testing", False),
            )

            if self.config.use_qubes_repo.get("version", None):
                files_inside_executor_with_placeholders += [
                    executor.get_plugins_dir()
                    / "chroot_archlinux/scripts/add-qubes-repository-key"
                ]
                cmd += [
                    f"sudo {executor.get_plugins_dir()}/chroot_archlinux/scripts/add-qubes-repository-key"
                ]

            # Create local repository inside chroot
            cmd += pacman_cmd + [
                f"sudo {executor.get_plugins_dir()}/build_archlinux/scripts/update-local-repo.sh {executor.get_cache_dir()}/qubes-x86_64/root {executor.get_repository_dir()}",
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

            build_command = [
                f"sudo qubes-x86_64-build -r {executor.get_cache_dir()} -- ",
                f"-d {executor.get_repository_dir()}:/builder/repository -- ",
                f"--syncdeps --noconfirm --skipinteg",
            ]

            cmd += [f"cd {source_dir}", " ".join(build_command)]

            try:
                executor.run(
                    cmd,
                    copy_in,
                    copy_out,
                    environment=self.environment,
                    files_inside_executor_with_placeholders=files_inside_executor_with_placeholders,
                )
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}:{build}: Failed to build PKGs: {str(e)}."
                raise BuildError(msg) from e

            # Get packages list that have been actually built from predicted ones
            packages_list = []
            for pkg in source_info["packages"]:
                if os.path.exists(pkgs_dir / pkg):
                    packages_list.append(pkg)

            info = source_info
            info.update(
                {
                    "packages": packages_list,
                    "source-hash": self.component.get_source_hash(),
                }
            )

            # Provision builder local repository
            provision_local_repository(
                build=build,
                component=self.component,
                dist=self.dist,
                repository_dir=repository_dir,
                packages_list=packages_list,
                build_artifacts_dir=artifacts_dir,
            )

            # Save package information we parsed for next stages
            self.save_dist_artifacts_info(stage=stage, basename=build_bn, info=info)


PLUGINS = [ArchlinuxBuildPlugin]
