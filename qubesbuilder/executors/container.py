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
import json
import subprocess
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import List, Tuple

from qubesbuilder.common import sanitize_line
from qubesbuilder.executors import Executor, log, ExecutorError

try:
    from docker import DockerClient
    from docker.errors import DockerException
except ImportError:
    DockerClient = None
    DockerException = ExecutorError

try:
    from podman import PodmanClient
    from podman.errors import PodmanError
except ImportError:
    PodmanClient = None
    PodmanError = ExecutorError


class ContainerExecutor(Executor):
    def __init__(self, container_client, image_name, **kwargs):
        self._container_client = container_client
        self._kwargs = kwargs
        if self._container_client == "podman":
            if PodmanClient is None:
                raise ExecutorError(f"Cannot find 'podman' on the system.")
            self._client = PodmanClient
        elif self._container_client == "docker":
            if DockerClient is None:
                raise ExecutorError(f"Cannot find 'docker' on the system.")
            self._client = DockerClient
        else:
            raise ExecutorError(f"Unknown container client '{self._container_client}'.")

        with self.get_client() as client:
            try:
                # Check if we have the image locally
                image = client.images.get(image_name)
                if not image:
                    # Try to pull the image
                    image = client.images.pull(image_name)
            except (PodmanError, DockerException) as e:
                raise ExecutorError(f"Cannot find {image_name}.") from e

        self.attrs = image.attrs

    @contextmanager
    def get_client(self):
        try:
            yield self._client(**self._kwargs)
        except (PodmanError, DockerException, ValueError) as e:
            raise ExecutorError("Cannot connect to container client.") from e

    def copy_in(self, container, source_path: Path, destination_dir: PurePath):
        src = source_path.resolve()
        dst = destination_dir.as_posix()

        cmd = [self._container_client, "cp", str(src), f"{container.id}:{dst}"]
        try:
            log.debug(f"copy-in (cmd): {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
        except subprocess.SubprocessError as e:
            raise ExecutorError from e

    def copy_out(self, container, source_path: PurePath, destination_dir: Path):
        src = source_path.as_posix()
        dst = destination_dir.resolve()

        cmd = [self._container_client, "cp", f"{container.id}:{src}", str(dst)]
        try:
            log.debug(f"copy-out (cmd): {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
        except subprocess.SubprocessError as e:
            raise ExecutorError from e

    def run(
        self,
        cmd: List[str],
        copy_in: List[Tuple[Path, PurePath]] = None,
        copy_out: List[Tuple[PurePath, Path]] = None,
        environment=None,
        no_fail_copy_out=False,
    ):

        container = None

        try:
            with self.get_client() as client:
                # prepare container for given image and command
                image = client.images.get(self.attrs["Id"])
                # FIXME: create a disposable container that will be removed after execution
                cmd = ["bash", "-c", "&&".join(cmd)]
                # FIXME: https://github.com/containers/podman/issues/11984
                if self._container_client == "podman":
                    for k, v in environment.copy().items():
                        environment[k] = str(v)
                container = client.containers.create(
                    image, cmd, privileged=True, environment=environment
                )
                log.info(f"Executing '{' '.join(cmd)}' in {container}...")

                # copy-in hook
                for src_in, dst_in in copy_in or []:
                    self.copy_in(container, source_path=src_in, destination_dir=dst_in)

                # FIXME: use attach method when podman-py will implement it
                # start and attach for streaming output
                process = subprocess.Popen(
                    [self._container_client, "start", "--attach", container.id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                while True:
                    if not process.stdout:
                        break
                    if process.poll() is not None:
                        break
                    for line in process.stdout:
                        log.info(f"output: {sanitize_line(line).rstrip()}")
                rc = process.poll()
                if rc != 0:
                    raise ExecutorError(f"Failed to run '{cmd}' (status={rc}).")

                # copy-out hook
                for src_out, dst_out in copy_out or []:
                    try:
                        self.copy_out(
                            container, source_path=src_out, destination_dir=dst_out
                        )
                    except ExecutorError as e:
                        # Ignore copy-out failure if requested
                        if no_fail_copy_out:
                            log.warning(f"File not found inside container: {src_out}.")
                            continue
                        raise e
        finally:
            if container:
                container.wait()
                container.remove()
