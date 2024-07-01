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

from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import ExecutorError
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.plugins import RPMDistributionPlugin
from qubesbuilder.plugins.chroot import ChrootError, ChrootPlugin


class RPMChrootPlugin(RPMDistributionPlugin, ChrootPlugin):
    """
    ChrootPlugin manages RPM chroot creation

    Stages:
        - chroot - Create Mock cache chroot.
    """

    name = "chroot_rpm"
    stages = ["init-cache"]

    def __init__(
        self,
        dist: QubesDistribution,
        config: Config,
        manager: PluginManager,
        **kwargs,
    ):
        super().__init__(dist=dist, config=config, manager=manager)

    def run(self, stage: str):
        """
        Run plugin for given stage.
        """

        if stage != "init-cache":
            return

        executor = self.get_executor(stage)

        mock_conf = f"{self.dist.fullname}-{self.dist.version}-{self.dist.architecture}.cfg"

        chroot_dir = self.get_cache_dir() / "chroot" / self.dist.name / "mock"
        chroot_dir.mkdir(exist_ok=True, parents=True)

        # FIXME: Parse from mock cfg?
        mock_chroot_name = mock_conf.replace(".cfg", "")

        # Delete previous chroot
        if (chroot_dir / mock_chroot_name).exists():
            shutil.rmtree(chroot_dir / mock_chroot_name)

        self.environment.update(
            {
                "DIST": self.dist.name,
                "PACKAGE_SET": self.dist.package_set,
            }
        )

        files_inside_executor_with_placeholders = [
            f"@PLUGINS_DIR@/chroot_rpm/mock/{mock_conf}"
        ]

        mock_cmd = [
            f"sudo --preserve-env=DIST,PACKAGE_SET,USE_QUBES_REPO_VERSION",
            f"/usr/libexec/mock/mock",
            f"--root {executor.get_plugins_dir()}/chroot_rpm/mock/{mock_conf}",
            "--disablerepo=builder-local",
        ]
        if isinstance(executor, ContainerExecutor):
            msg = (
                f"{self.dist}: Mock isolation set to 'simple', build has full network "
                f"access. Use 'qubes' executor for network-isolated build."
            )
            self.log.warning(msg)
            mock_cmd.append("--isolation=simple")
        else:
            mock_cmd.append("--isolation=nspawn")
        if self.config.verbose:
            mock_cmd.append("--verbose")

        # Create a first cage to generate the mock chroot
        copy_in = self.default_copy_in(
            executor.get_plugins_dir(), executor.get_sources_dir()
        )
        copy_out = [
            (
                executor.get_cache_dir() / f"mock/{mock_chroot_name}",
                chroot_dir,
            )
        ]
        cmd = [" ".join(mock_cmd + ["--init"])]
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
            raise ChrootError(msg) from e

        # Create a second cage for downloading the packages
        additional_packages = (
            self.config.get("cache", {})
            .get(self.dist.distribution, {})
            .get("packages", [])
        )
        if additional_packages:
            # Remove dnf_cache
            if (chroot_dir / mock_chroot_name / "dnf_cache").exists():
                shutil.rmtree(chroot_dir / mock_chroot_name / "dnf_cache")
            copy_in = self.default_copy_in(
                executor.get_plugins_dir(), executor.get_sources_dir()
            ) + [
                (
                    chroot_dir / mock_chroot_name,
                    executor.get_cache_dir() / f"mock",
                ),
            ]
            copy_out = [
                (
                    executor.get_cache_dir()
                    / f"mock/{mock_chroot_name}/dnf_cache",
                    chroot_dir / mock_chroot_name,
                )
            ]
            for package in additional_packages:
                mock_cmd += ["--install", package]
            cmd.append(" ".join(mock_cmd))
            try:
                executor.run(
                    cmd,
                    copy_in,
                    copy_out,
                    environment=self.environment,
                    files_inside_executor_with_placeholders=files_inside_executor_with_placeholders,
                )
            except ExecutorError as e:
                msg = (
                    f"{self.dist}: Failed to download extra packages: {str(e)}."
                )
                raise ChrootError(msg) from e


PLUGINS = [RPMChrootPlugin]
