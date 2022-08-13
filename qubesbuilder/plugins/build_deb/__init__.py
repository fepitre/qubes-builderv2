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

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
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
    target_dir = repository_dir / f"{component.name}_{component.version}"
    if target_dir.exists():
        shutil.rmtree(target_dir.as_posix())
    target_dir.mkdir(parents=True)

    try:
        debian_source_files = ["dsc", "debian"]
        if source_info["package-type"] == "quilt":
            debian_source_files.append("orig")

        # deb
        files = [build_artifacts_dir / deb for deb in packages_list]
        files += [build_artifacts_dir / source_info[f] for f in debian_source_files]

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
    DEBBuildPlugin manages Debian distribution build.

    Stages:
        - build - Build Debian packages and provision local repository.

    Entry points:
        - build
    """

    plugin_dependencies = ["source_deb", "build"]

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
            executor=executor,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
            use_qubes_repo=use_qubes_repo,
            backend_vmm=backend_vmm,
        )

    def run(self, stage: str):
        """
        Run plugin for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        if stage != "build":
            return

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
                f"{self.component}:{self.dist}: Source hash is the same than already built source. Skipping."
            )
            return

        # Clean previous build artifacts
        if artifacts_dir.exists():
            shutil.rmtree(artifacts_dir.as_posix())
        artifacts_dir.mkdir(parents=True)

        # Source artifacts
        prep_artifacts_dir = self.get_dist_component_artifacts_dir(stage="prep")

        repository_dir = self.get_repository_dir() / self.dist.distribution
        repository_dir.mkdir(parents=True, exist_ok=True)

        # Remove previous versions in order to keep the latest one only
        for build in repository_dir.glob(f"{self.component.name}_*"):
            shutil.rmtree(build.as_posix())

        for directory in self.parameters["build"]:
            # directory basename will be used as prefix for some artifacts
            directory_bn = directory.mangle()

            # Read information from source stage
            source_info = self.get_dist_artifacts_info(
                stage="prep", basename=directory_bn
            )

            #
            # Build Debian packages
            #

            debian_source_files = ["dsc", "debian"]
            if not source_info.get("package-type", None):
                raise BuildError(
                    f"Cannot determine source type. Missing 'prep' stage call?"
                )
            if source_info["package-type"] == "quilt":
                debian_source_files.append("orig")
            for src in debian_source_files:
                if not source_info.get(src, None):
                    raise BuildError(f"Cannot find sources for '{directory}'")

            # Copy-in plugin, repository and sources
            copy_in = [
                (self.plugins_dir / "build_deb", self.executor.get_plugins_dir()),
                (
                    self.plugins_dir / "source_deb" / "pbuilder",
                    self.executor.get_builder_dir(),
                ),
                (repository_dir, self.executor.get_repository_dir()),
            ]

            copy_in += [
                (prep_artifacts_dir / source_info[f], self.executor.get_build_dir())
                for f in debian_source_files
            ]

            # Copy-in plugin dependencies
            copy_in += [
                (self.plugins_dir / plugin, self.executor.get_plugins_dir())
                for plugin in self.plugin_dependencies
            ]

            # Files inside executor
            files_inside_executor_with_placeholders = [
                self.executor.get_builder_dir() / "pbuilder/pbuilderrc"
            ]

            results_dir = self.executor.get_builder_dir() / "pbuilder" / "results"
            source_info["changes"] = source_info["dsc"].replace(
                ".dsc", "_amd64.changes"
            )
            source_info["buildinfo"] = source_info["dsc"].replace(
                ".dsc", "_amd64.buildinfo"
            )
            copy_out = [
                (
                    results_dir / source_info["dsc"].replace(".dsc", "_amd64.changes"),
                    artifacts_dir,
                ),
                (
                    results_dir
                    / source_info["dsc"].replace(".dsc", "_amd64.buildinfo"),
                    artifacts_dir,
                ),
            ]
            # We prefer to keep originally copied in source to cross-check
            # what's inside the resulting .changes file.
            # copy_out += [
            #     (results_dir / source_info[f], artifacts_dir) for f in debian_source_files
            # ]
            copy_out += [
                (results_dir / deb, artifacts_dir) for deb in source_info["packages"]
            ]

            # Create local builder repository
            extra_sources = (
                f"deb [trusted=yes] file:///tmp/qubes-deb {self.dist.name} main"
            )
            # extra_sources = ""
            cmd = [
                f"{self.executor.get_plugins_dir()}/build_deb/scripts/create-local-repo {self.executor.get_repository_dir()} {self.dist.fullname} {self.dist.name}"
            ]

            if self.use_qubes_repo.get("version", None):
                qubes_version = self.use_qubes_repo["version"]
                extra_sources = f"{extra_sources}|deb [arch=amd64] http://deb.qubes-os.org/r{qubes_version}/vm {self.dist.name} main"
                cmd += [
                    f"gpg --dearmor "
                    f"< {self.executor.get_plugins_dir()}/source_deb/keys/qubes-debian-r{qubes_version}.asc "
                    f"> {self.executor.get_builder_dir()}/pbuilder/qubes-keyring.gpg"
                ]
                if self.use_qubes_repo.get("testing", False):
                    extra_sources = f"{extra_sources}|deb [arch=amd64] http://deb.qubes-os.org/r{qubes_version}/vm {self.dist.name}-testing main"

            # fmt: off
            # FIXME: We disable black here because it removes escaped quotes.
            #  This is until we use shlex.quote.

            # Add prepared chroot cache
            base_tgz = self.get_cache_dir() / "chroot" / self.dist.name / "base.tgz"
            if base_tgz.exists():
                copy_in += [
                    (base_tgz, self.executor.get_builder_dir() / "pbuilder")
                ]
                cmd += [
                    f"sudo -E pbuilder update "
                    f"--distribution {self.dist.name} "
                    f"--configfile {self.executor.get_builder_dir()}/pbuilder/pbuilderrc "
                    f"--othermirror \"{extra_sources}\""
                ]
            else:
                cmd += [
                    f"sudo -E pbuilder create "
                    f"--distribution {self.dist.name} "
                    f"--configfile {self.executor.get_builder_dir()}/pbuilder/pbuilderrc "
                    f"--othermirror \"{extra_sources}\""
                ]

            cmd += [
                f"sudo -E pbuilder build --override-config "
                f"--distribution {self.dist.name} "
                f"--configfile {self.executor.get_builder_dir()}/pbuilder/pbuilderrc "
                f"--othermirror \"{extra_sources}\" "
                f"{str(self.executor.get_build_dir() / source_info['dsc'])}"
            ]
            # fmt: on
            try:
                self.executor.run(
                    cmd,
                    copy_in,
                    copy_out,
                    environment=self.environment,
                    no_fail_copy_out=True,
                    files_inside_executor_with_placeholders=files_inside_executor_with_placeholders,
                )
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}:{directory}: Failed to build packages: {str(e)}."
                raise BuildError(msg) from e

            # Get packages list that have been actually built from predicted ones
            packages_list = []
            for deb in source_info["packages"]:
                if os.path.exists(artifacts_dir / deb):
                    packages_list.append(deb)

            # We prefer to keep originally copied in source to cross-check
            # what's inside the resulting .changes file.
            files = [prep_artifacts_dir / source_info[f] for f in debian_source_files]
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
            info = source_info
            info["packages"] = packages_list
            info["source-hash"] = self.component.get_source_hash()
            self.save_dist_artifacts_info(stage=stage, basename=directory_bn, info=info)
