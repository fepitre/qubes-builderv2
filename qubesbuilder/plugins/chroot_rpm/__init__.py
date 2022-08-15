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
from pathlib import Path

from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.log import get_logger
from qubesbuilder.plugins.chroot import ChrootError, ChrootPlugin

log = get_logger("chroot_rpm")


class RPMChrootPlugin(ChrootPlugin):
    """
    ChrootPlugin manages RPM chroot creation

    Stages:
        - chroot - Create Mock cache chroot.
    """

    plugin_dependencies = ["source_rpm"]

    def __init__(
        self,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(
            dist=dist,
            executor=executor,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )

    def run(self, stage: str):
        """
        Run plugin for given stage.
        """

        if stage != "init-cache":
            return

        mock_conf = (
            f"{self.dist.fullname}-{self.dist.version}-{self.dist.architecture}.cfg"
        )

        chroot_dir = self.get_cache_dir() / "chroot" / self.dist.name
        chroot_dir.mkdir(exist_ok=True, parents=True)

        # FIXME: Parse from mock cfg?
        mock_chroot_name = mock_conf.replace(".cfg", "")
        if (chroot_dir / mock_chroot_name).exists():
            shutil.rmtree(chroot_dir / mock_chroot_name)

        copy_in = [
            (self.plugins_dir / dependency, self.executor.get_plugins_dir())
            for dependency in self.plugin_dependencies
        ]

        self.environment.update(
            {
                "DIST": self.dist.name,
                "PACKAGE_SET": self.dist.package_set,
            }
        )

        copy_out = [
            (
                Path(f"{self.executor.get_builder_dir()}/mock/{mock_chroot_name}"),
                chroot_dir,
            )
        ]

        mock_cmd = [
            f"sudo --preserve-env=DIST,PACKAGE_SET,USE_QUBES_REPO_VERSION",
            f"/usr/libexec/mock/mock",
            f"--root {self.executor.get_plugins_dir()}/source_rpm/mock/{mock_conf}",
            "--disablerepo=builder-local",
            "--init",
        ]
        if isinstance(self.executor, ContainerExecutor):
            msg = (
                f"{self.dist}: Mock isolation set to 'simple', build has full network "
                f"access. Use 'qubes' executor for network-isolated build."
            )
            log.warning(msg)
            mock_cmd.append("--isolation=simple")
        else:
            mock_cmd.append("--isolation=nspawn")
        if self.verbose:
            mock_cmd.append("--verbose")

        files_inside_executor_with_placeholders = [
            f"{self.executor.get_plugins_dir()}/source_rpm/mock/{mock_conf}"
        ]
        cmd = [" ".join(mock_cmd)]

        try:
            self.executor.run(
                cmd,
                copy_in,
                copy_out,
                environment=self.environment,
                files_inside_executor_with_placeholders=files_inside_executor_with_placeholders,
            )
        except ExecutorError as e:
            msg = f"{self.dist}: Failed to generate chroot: {str(e)}."
            raise ChrootError(msg) from e
