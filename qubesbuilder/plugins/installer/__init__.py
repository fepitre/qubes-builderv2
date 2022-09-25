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
import itertools
import shutil
from datetime import datetime
from typing import Dict

import yaml

from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import ExecutorError
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import (
    PluginError,
    DistributionPlugin,
)

log = get_logger("installer")


class InstallerError(PluginError):
    pass


class InstallerPlugin(DistributionPlugin):
    """
    InstallerPlugin creates Qubes OS ISO
    """

    dependencies = ["source_rpm"]

    def __init__(
        self,
        dist: QubesDistribution,
        config: Config,
        manager: PluginManager,
        **kwargs,
    ):
        super().__init__(config=config, manager=manager, dist=dist)

        self.iso_name = ""
        self.iso_version = ""

        if not (
            self.manager.entities["installer"].directory
            / self.config.installer_kickstart
        ).exists():
            raise InstallerError(
                f"Cannot find kickstart: '{self.config.installer_kickstart}'"
            )

    def update_parameters(self, stage: str):
        executor = self.config.get_executor_from_config(stage_name=stage)
        self.environment.update(
            {
                "DIST": self.dist.name,
                "INSTALL_DIR": f"{executor.get_builder_dir()}/mnt",
                "ARTIFACTS_DIR": str(executor.get_build_dir()),
                "PLUGINS_DIR": str(executor.get_plugins_dir()),
                "PACKAGES_DIR": str(executor.get_repository_dir()),
                "CACHE_DIR": str(executor.get_cache_dir()),
                "ISO_USE_KERNEL_LATEST": "1"
                if self.config.iso_use_kernel_latest
                else "0",
            }
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

        if self.config.qubes_release:
            self.iso_version = self.config.qubes_release.upper()
            self.environment["QUBES_RELEASE"] = self.config.qubes_release
        else:
            self.iso_version = datetime.utcnow().strftime("%Y%m%d")

        if self.config.iso_flavor:
            self.environment["ISO_FLAVOR"] = self.config.iso_flavor
            self.iso_name = f"Qubes-{self.iso_version}-{self.config.iso_flavor}-{self.dist.architecture}"
        else:
            self.iso_name = f"Qubes-{self.iso_version}-{self.dist.architecture}"

        self.environment.update(
            {"ISO_VERSION": self.iso_version, "ISO_NAME": self.iso_name}
        )

        # Kickstart will be copied under builder directory
        self.environment[
            "INSTALLER_KICKSTART"
        ] = f"{executor.get_plugins_dir()}/installer/{self.config.installer_kickstart}"

    def get_artifacts_info(self, stage: str) -> Dict:
        fileinfo = (
            self.get_installer_dir() / f"{self.dist.name}_{self.iso_name}.{stage}.yml"
        )
        if fileinfo.exists():
            try:
                with open(fileinfo, "r") as f:
                    artifacts_info = yaml.safe_load(f.read())
                return artifacts_info or {}
            except (PermissionError, yaml.YAMLError) as e:
                msg = f"{self.dist}: Failed to read info from {stage} stage."
                raise PluginError(msg) from e
        return {}

    def save_artifacts_info(self, stage: str, info: dict):
        artifacts_dir = self.get_installer_dir()
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(
                artifacts_dir / f"{self.dist.name}_{self.iso_name}.{stage}.yml", "w"
            ) as f:
                f.write(yaml.safe_dump(info))
        except (PermissionError, yaml.YAMLError) as e:
            msg = f"{self.dist}: Failed to write info for {stage} stage."
            raise PluginError(msg) from e

    def delete_artifacts_info(self, stage: str):
        artifacts_dir = self.get_installer_dir()
        info_path = artifacts_dir / f"{self.dist.name}_{self.iso_name}.{stage}.yml"
        if info_path.exists():
            info_path.unlink()

    def get_env(self):
        env = []
        for key, val in self.environment.items():
            env.append(f'{key}="{val}"')
        return " ".join(env)

    def run(self, stage: str):
        self.update_parameters(stage)

        executor = self.config.get_executor_from_config(stage_name=stage)

        mock_conf = (
            f"{self.dist.fullname}-{self.dist.version}-{self.dist.architecture}.cfg"
        )
        repository_dir = self.get_repository_dir() / self.dist.distribution

        cache_dir = self.get_cache_dir() / "installer"
        chroot_cache = (
            self.get_cache_dir()
            / "installer/chroot/mock"
            / mock_conf.replace(".cfg", "")
        )
        iso_cache = cache_dir / self.iso_name

        iso_dir = self.get_iso_dir()
        iso_dir.mkdir(parents=True, exist_ok=True)
        iso = iso_dir / f"{self.iso_name}.iso"

        if iso.exists() and stage in ("prep", "build"):
            msg = f"{self.dist}:{self.iso_name}: ISO already exists."
            raise InstallerError(msg)

        if not iso.exists() and stage in ("sign", "upload"):
            msg = f"{self.iso_name}: Cannot find ISO '{iso}'."
            raise InstallerError(msg)

        if stage == "init-cache":
            chroot_dir = cache_dir / "chroot/mock"
            chroot_dir.mkdir(exist_ok=True, parents=True)

            # FIXME: Parse from mock cfg?
            mock_chroot_name = mock_conf.replace(".cfg", "")
            if (chroot_dir / mock_chroot_name).exists():
                shutil.rmtree(chroot_dir / mock_chroot_name)

            copy_in = [
                (
                    self.manager.entities["installer"].directory,
                    executor.get_plugins_dir(),
                ),
            ] + [
                (self.manager.entities[plugin].directory, executor.get_plugins_dir())
                for plugin in self.dependencies
            ]

            # Copy-in builder local repository
            if repository_dir.exists():
                copy_in += [(repository_dir, executor.get_repository_dir())]

            copy_out = [
                (
                    executor.get_cache_dir() / f"mock/{mock_chroot_name}",
                    chroot_dir,
                )
            ]

            # Prepare cmd
            cmd = []

            mock_cmd = [
                f"sudo --preserve-env=DIST,USE_QUBES_REPO_VERSION",
                f"/usr/libexec/mock/mock",
                f"--root {executor.get_plugins_dir()}/installer/mock/{mock_conf}",
                "--init",
            ]
            if isinstance(executor, ContainerExecutor):
                msg = (
                    f"{self.dist}: Mock isolation set to 'simple', build has full network "
                    f"access. Use 'qubes' executor for network-isolated build."
                )
                log.warning(msg)
                mock_cmd.append("--isolation=simple")
            else:
                mock_cmd.append("--isolation=nspawn")
            if self.config.verbose:
                mock_cmd.append("--verbose")
            if self.config.use_qubes_repo and self.config.use_qubes_repo.get("version"):
                mock_cmd.append("--enablerepo=qubes-current")
            if self.config.use_qubes_repo and self.config.use_qubes_repo.get("testing"):
                mock_cmd.append("--enablerepo=qubes-current-testing")

            files_inside_executor_with_placeholders = [
                f"{executor.get_plugins_dir()}/installer/mock/{mock_conf}"
            ]

            # Create builder-local repository (could be empty) inside the cage
            cmd += [
                f"mkdir -p {executor.get_repository_dir()}",
                f"cd {executor.get_repository_dir()}",
                "createrepo_c .",
            ]

            cmd += [" ".join(mock_cmd)]

            try:
                executor.run(
                    cmd,
                    copy_in,
                    copy_out,
                    environment=self.environment,
                    files_inside_executor_with_placeholders=files_inside_executor_with_placeholders,
                )
            except ExecutorError as e:
                msg = f"{self.dist}: Failed to generate chroot: {str(e)}."
                raise InstallerError(msg) from e

        if stage == "prep":
            copy_in = [
                (
                    self.manager.entities["installer"].directory,
                    executor.get_plugins_dir(),
                )
            ] + [
                (self.manager.entities[plugin].directory, executor.get_plugins_dir())
                for plugin in self.dependencies
            ]

            # Copy-in builder local repository
            if repository_dir.exists():
                copy_in += [(repository_dir, executor.get_repository_dir())]

            # Prepare cmd
            cmd = []

            # Add prepared chroot cache
            if chroot_cache.exists():
                copy_in += [(chroot_cache.parent, executor.get_cache_dir())]
                cmd += [f"sudo chown -R root:mock {executor.get_cache_dir() / 'mock'}"]

            # Keep packages needed for generating the ISO in a fresh cache
            if iso_cache.exists():
                shutil.rmtree(iso_cache)
            iso_cache.mkdir(parents=True)

            copy_out = [
                (
                    executor.get_plugins_dir() / f"installer/work",
                    cache_dir / self.iso_name,
                ),
                (
                    executor.get_plugins_dir() / f"installer/yum/installer/rpm",
                    cache_dir / self.iso_name,
                ),
                (
                    executor.get_builder_dir()
                    / f"dnfroot/etc/yum.repos.d/installer.repo",
                    cache_dir / self.iso_name,
                ),
            ]

            #
            # Inside mock chroot to generate our packages list (qubes-pykickstart)
            #

            mock_cmd = [
                f"sudo --preserve-env={','.join(self.environment.keys())}",
                f"/usr/libexec/mock/mock",
                f"--root {executor.get_plugins_dir()}/installer/mock/{mock_conf}",
                f"--chroot 'env {self.get_env()} make -C {executor.get_plugins_dir()}/installer iso-prepare iso-parse-kickstart iso-parse-tmpl'",
            ]
            if isinstance(executor, ContainerExecutor):
                msg = (
                    f"{self.dist}: Mock isolation set to 'simple', build has full network "
                    f"access. Use 'qubes' executor for network-isolated build."
                )
                log.warning(msg)
                mock_cmd.append("--isolation=simple")
            else:
                mock_cmd.append("--isolation=nspawn")
            if self.config.verbose:
                mock_cmd.append("--verbose")
            if self.config.use_qubes_repo and self.config.use_qubes_repo.get("version"):
                mock_cmd.append("--enablerepo=qubes-current")
            if self.config.use_qubes_repo and self.config.use_qubes_repo.get("testing"):
                mock_cmd.append("--enablerepo=qubes-current-testing")
            if chroot_cache.exists():
                mock_cmd.append("--plugin-option=root_cache:age_check=False")

            # Create builder-local repository inside the cage
            if not repository_dir.exists():
                mock_cmd.append("--disablerepo=builder-local")

            files_inside_executor_with_placeholders = [
                f"{executor.get_plugins_dir()}/installer/mock/{mock_conf}"
            ]

            cmd += [" ".join(mock_cmd)]

            #
            # Outside mock chroot to use the latest packages (dnf, openssl, etc.) from the cage.
            #

            cmd += [
                f"sudo --preserve-env={','.join(self.environment.keys())} "
                f"make -C {executor.get_plugins_dir()}/installer "
                f"iso-prepare iso-packages-anaconda iso-packages-lorax",
            ]

            try:
                executor.run(
                    cmd,
                    copy_in,
                    copy_out,
                    environment=self.environment,
                    files_inside_executor_with_placeholders=files_inside_executor_with_placeholders,
                )
            except ExecutorError as e:
                msg = f"{self.dist}: Failed to prepare installer: {str(e)}."
                raise InstallerError(msg) from e

            # Check we have only RPMs in installer (Lorax) and work (Anaconda) repositories
            for f in itertools.chain(
                (cache_dir / self.iso_name / "rpm").glob("*"),
                (
                    cache_dir
                    / f"{self.iso_name}/work/{self.iso_version}/{self.dist.architecture}/os/Packages"
                ).glob("*"),
            ):
                if f.suffix != ".rpm":
                    raise InstallerError(
                        f"File with forbidden extension detected: '{f}'."
                    )

        if stage == "build":
            copy_in = [
                (
                    self.manager.entities["installer"].directory,
                    executor.get_plugins_dir(),
                ),
                (
                    cache_dir / self.iso_name / "work",
                    executor.get_plugins_dir() / "installer",
                ),
                (
                    cache_dir / self.iso_name / "rpm",
                    executor.get_plugins_dir() / "installer/yum/installer",
                ),
            ] + [
                (self.manager.entities[plugin].directory, executor.get_plugins_dir())
                for plugin in self.dependencies
            ]

            # Copy-in builder local repository
            if repository_dir.exists():
                copy_in += [(repository_dir, executor.get_repository_dir())]

            # Prepare installer cmd
            cmd = []

            # Add prepared chroot cache
            if chroot_cache.exists():
                copy_in += [(chroot_cache.parent, executor.get_cache_dir())]
                cmd += [f"sudo chown -R root:mock {executor.get_cache_dir() / 'mock'}"]

            copy_out = [
                (
                    executor.get_plugins_dir()
                    / f"installer/work/{self.iso_version}/{self.dist.architecture}/iso/{self.iso_name}.iso",
                    iso_dir,
                )
            ]

            # Create builder-local repository (could be empty) inside the cage
            cmd += [
                f"mkdir -p {executor.get_repository_dir()}",
                f"cd {executor.get_repository_dir()}",
                "createrepo_c .",
            ]

            #
            # Inside mock chroot to use qubes-lorax
            #

            mock_cmd = [
                f"sudo --preserve-env={','.join(self.environment.keys())}",
                f"/usr/libexec/mock/mock",
                f"--root {executor.get_plugins_dir()}/installer/mock/{mock_conf}",
                "--disablerepo='*'",
                f"--chroot 'env {self.get_env()} make -C {executor.get_plugins_dir()}/installer iso-prepare iso-parse-kickstart iso-installer-lorax iso-installer-mkisofs'",
            ]
            if isinstance(executor, ContainerExecutor):
                msg = (
                    f"{self.dist}: Mock isolation set to 'simple', build has full network "
                    f"access. Use 'qubes' executor for network-isolated build."
                )
                log.warning(msg)
                mock_cmd.append("--isolation=simple")
            else:
                mock_cmd.append("--isolation=nspawn")
            if self.config.verbose:
                mock_cmd.append("--verbose")
            if chroot_cache.exists():
                mock_cmd.append("--plugin-option=root_cache:age_check=False")

            files_inside_executor_with_placeholders = [
                f"{executor.get_plugins_dir()}/installer/mock/{mock_conf}"
            ]

            cmd += [" ".join(mock_cmd)]

            try:
                executor.run(
                    cmd,
                    copy_in,
                    copy_out,
                    environment=self.environment,
                    files_inside_executor_with_placeholders=files_inside_executor_with_placeholders,
                )
            except ExecutorError as e:
                msg = f"{self.dist}: Failed to create ISO: {str(e)}."
                raise InstallerError(msg) from e

            # Save ISO information we built
            info = {
                "iso": iso.name,
                "kickstart": str(self.config.installer_kickstart),
                "packages": {
                    "runtime": [
                        pkg.name
                        for pkg in (cache_dir / self.iso_name / "rpm").glob("*.rpm")
                    ],
                    "anaconda": [
                        pkg.name
                        for pkg in (
                            cache_dir
                            / f"{self.iso_name}/work/{self.iso_version}/{self.dist.architecture}/os/Packages"
                        ).glob("*.rpm")
                    ],
                },
            }
            self.save_artifacts_info(stage, info)

        if stage == "sign":
            # Check if we have a signing key provided
            sign_key = self.config.sign_key.get("iso", None)
            if not sign_key:
                log.info(f"{self.dist}: No signing key found.")
                return

            # Check if we have a gpg client provided
            if not self.config.gpg_client:
                log.info(f"Please specify GPG client to use!")
                return

            try:
                log.info(f"{self.iso_name}: Signing '{iso.name}'.")
                cmd = [
                    f"{self.manager.entities['installer'].directory}/scripts/release-iso {iso} {self.config.gpg_client} {sign_key}"
                ]
                executor.run(cmd)
            except ExecutorError as e:
                msg = f"{self.iso_name}: Failed to sign ISO '{iso}'."
                raise InstallerError(msg) from e

        if stage == "upload":
            remote_path = self.config.repository_upload_remote_host.get("iso", None)
            if not remote_path:
                log.info(f"{self.dist}: No remote location defined. Skipping.")
                return

            try:
                cmd = [
                    f"rsync --partial --progress --hard-links -air --mkpath -- {iso_dir}/ {remote_path}"
                ]
                executor.run(cmd)
            except ExecutorError as e:
                raise InstallerError(
                    f"{self.dist}: Failed to upload to remote host: {str(e)}"
                ) from e
