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
import shutil
import subprocess
import getpass

from pathlib import Path
from typing import List, Tuple

from qubesbuilder.common import sanitize_line
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger

log = get_logger("executor:local")


class LocalExecutor(Executor):
    """
    Local executor
    """

    def __init__(self, **kwargs):
        self._kwargs = kwargs

    def copy_in(self, source_path: Path, destination_dir: Path):  # type: ignore
        src = source_path.resolve()
        dst = destination_dir.resolve()
        try:
            if src.is_dir():
                dst = dst / src.name
                if dst.exists():
                    shutil.rmtree(str(dst))
                shutil.copytree(str(src), str(dst))
            else:
                shutil.copy2(str(src), str(dst))
        except (shutil.Error, FileExistsError, FileNotFoundError) as e:
            raise ExecutorError from e

    def copy_out(self, source_path: Path, destination_dir: Path):  # type: ignore
        self.copy_in(source_path, destination_dir)

    def run(  # type: ignore
        self,
        cmd: List[str],
        copy_in: List[Tuple[Path, Path]] = None,
        copy_out: List[Tuple[Path, Path]] = None,
        environment=None,
        no_fail_copy_out=False,
    ):

        # FIXME: ensure to create /builder tree layout in all executors
        if self._kwargs.get("group", None):
            chown = f"{self._kwargs.get('user', getpass.getuser())}:{self._kwargs.get('group', 'user')}"
        else:
            chown = self._kwargs.get("user", getpass.getuser())

        cmd = [
            "sudo mkdir -p /builder",
            f"sudo chown -R {chown} /builder",
        ] + cmd
        cmd = ["bash", "-c", "&&".join(cmd)]

        log.info(f"Executing '{' '.join(cmd)}'.")

        # copy-in hook
        for src, dst in copy_in or []:
            self.copy_in(source_path=src, destination_dir=dst)

        # stream output for command
        process = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environment
        )
        while True:
            if not process.stdout:
                log.error(f"No output!")
                break
            if process.poll() is not None:
                break
            for line in process.stdout:
                line = sanitize_line(line.rstrip(b"\n")).rstrip()
                log.info(f"output: {str(line)}")
        rc = process.poll()
        if rc != 0:
            raise ExecutorError(f"Failed to run '{cmd}' (status={rc}).")

        # copy-out hook
        for src, dst in copy_out or []:
            try:
                self.copy_out(source_path=src, destination_dir=dst)
            except ExecutorError as e:
                # Ignore copy-out failure if requested
                if no_fail_copy_out:
                    log.warning(f"File not found inside container: {src}.")
                    continue
                raise e
