# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2023 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
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
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import ArchlinuxDistributionPlugin
from qubesbuilder.plugins.chroot import ChrootError, ChrootPlugin

log = get_logger("chroot_archlinux")


class ArchlinuxChrootPlugin(ArchlinuxDistributionPlugin, ChrootPlugin):
    """
    ArchlinuxChrootPlugin manages Archlinux chroot creation

    Stages:
        - chroot - Create Archlinux cache chroot.
    """

    stages = ["init-cache"]

    def __init__(
        self,
        dist: QubesDistribution,
        config: Config,
        manager: PluginManager,
        **kwargs,
    ):
        super().__init__(dist=dist, config=config, manager=manager)

    @staticmethod
    def get_base_cmd(chroot_dir):
        mkarchchroot_cmd = [
            "sudo",
            "mkarchroot",
            "-C",
            "/usr/share/devtools/pacman-extra.conf",
            "-M",
            "/usr/share/devtools/makepkg-x86_64.conf",
            chroot_dir,
            "base-devel",
        ]

        cmd = [
            "sudo pacman-key --init",
            "sudo pacman-key --populate",
            " ".join(mkarchchroot_cmd),
        ]

        return cmd

    def run(self, stage: str):
        """
        Run plugin for given stage.
        """

        if stage != "init-cache":
            return

        executor = self.config.get_executor_from_config(stage)

        chroot_dir = self.get_cache_dir() / "chroot" / self.dist.name
        chroot_dir.mkdir(exist_ok=True, parents=True)
        chroot_name = "root"
        chroot_archive = f"{chroot_name}.tar.gz"
        if (chroot_dir / chroot_archive).exists():
            shutil.rmtree(chroot_dir / chroot_archive)

        copy_in = [
            (self.manager.entities[dependency].directory, executor.get_plugins_dir())
            for dependency in self.dependencies
        ]

        self.environment.update(
            {
                "DIST": self.dist.name,
                "PACKAGE_SET": self.dist.package_set,
            }
        )

        copy_out = [
            (
                executor.get_cache_dir() / chroot_archive,
                chroot_dir,
            )
        ]

        chroot_dir = str(executor.get_cache_dir() / chroot_name)

        cmd = self.get_base_cmd(chroot_dir) + [
            f"cd {executor.get_cache_dir()}",
            f"sudo tar cvf {chroot_archive} {chroot_name}",
        ]

        try:
            executor.run(
                cmd,
                copy_in,
                copy_out,
                environment=self.environment,
            )
        except ExecutorError as e:
            msg = f"{self.dist}: Failed to generate chroot: {str(e)}."
            raise ChrootError(msg) from e


PLUGINS = [ArchlinuxChrootPlugin]
