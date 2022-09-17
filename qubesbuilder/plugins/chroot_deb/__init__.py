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
import os

from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import ExecutorError
from qubesbuilder.helpers import PluginManager
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import DEBDistributionPlugin
from qubesbuilder.plugins.chroot import ChrootPlugin, ChrootError

log = get_logger("chroot_deb")


class DEBChrootPlugin(DEBDistributionPlugin, ChrootPlugin):
    """
    ChrootPlugin manages Debian chroot creation

    Stages:
        - chroot - Create pbuilder base.tgz.
    """

    stages = ["init-cache"]
    dependencies = ["source_deb"]

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

        executor = self.config.get_executor_from_config(stage)

        chroot_dir = self.get_cache_dir() / "chroot" / self.dist.name / "pbuilder"
        chroot_dir.mkdir(exist_ok=True, parents=True)

        if (chroot_dir / "base.tgz").exists():
            os.remove(chroot_dir / "base.tgz")

        copy_in = [
            (self.manager.entities[dependency].directory, executor.get_plugins_dir())
            for dependency in self.dependencies
        ]

        copy_in += [
            (
                self.manager.entities["source_deb"].directory / "pbuilder",
                executor.get_builder_dir(),
            ),
        ]
        copy_out = [
            (
                executor.get_builder_dir() / "pbuilder/base.tgz",
                chroot_dir,
            )
        ]
        files_inside_executor_with_placeholders = [
            executor.get_builder_dir() / "pbuilder/pbuilderrc"
        ]
        cmd = [
            f"sed -i '\#/tmp/qubes-deb#d' {executor.get_builder_dir()}/pbuilder/pbuilderrc",
            f"sudo -E pbuilder create --distribution {self.dist.name} "
            f"--configfile {executor.get_builder_dir()}/pbuilder/pbuilderrc",
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
            msg = f"{self.dist}: Failed to generate chroot: {str(e)}."
            raise ChrootError(msg) from e


PLUGINS = [DEBChrootPlugin]
