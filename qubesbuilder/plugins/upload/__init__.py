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

from pathlib import Path

from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor
from qubesbuilder.executors.local import LocalExecutor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import Plugin, PluginError

log = get_logger("upload")


class UploadError(PluginError):
    pass


class UploadPlugin(Plugin):
    """
    UploadPlugin manages generic distribution upload.
    """

    def __init__(
        self,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        qubes_release: str,
        repository_upload_remote_host: dict,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )

        self.executor = executor
        self.dist = dist
        self.qubes_release = qubes_release
        self.repository_upload_remote_host = repository_upload_remote_host

    def run(self, stage: str):
        if stage == "upload":
            if not isinstance(self.executor, LocalExecutor):
                raise UploadError("This plugin only supports local executor.")
            remote_path = self.repository_upload_remote_host.get(self.dist.type, None)
            if not remote_path:
                log.info(f"{self.dist}: No remote location defined. Skipping.")
                return
            try:
                local_path = (
                    self.get_repository_publish_dir()
                    / self.dist.type
                    / self.qubes_release
                )
                # For 'deb' we don't sync 'db' and 'conf' folders.
                cmd = [
                    f"rsync --partial --progress --hard-links -air --exclude=db --exclude=conf -- {local_path}/ {remote_path}/"
                ]
                self.executor.run(cmd)
            except ExecutorError as e:
                raise UploadError(
                    f"{self.dist}: Failed to upload to remote host: {str(e)}"
                ) from e
