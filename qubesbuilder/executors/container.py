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
import subprocess
from contextlib import contextmanager
from pathlib import Path, PurePath
from typing import List, Tuple

try:
    from docker import DockerClient
    from docker.errors import DockerException
except ImportError:
    DockerClient = None
    DockerException = Exception

try:
    from podman import PodmanClient
    from podman.errors import PodmanError
except ImportError:
    PodmanClient = None
    PodmanError = Exception

from qubesbuilder.executors import Executor, log, ExecutorException


class ContainerExecutor(Executor):

    def __init__(self, container_client, image_name, **kwargs):
        self._container_client = container_client
        self._kwargs = kwargs
        if self._container_client == "podman":
            if PodmanClient is None:
                raise ExecutorException(f"Cannot find 'podman' on the system.")
            self._client = PodmanClient
        elif self._container_client == "docker":
            if DockerClient is None:
                raise ExecutorException(f"Cannot find 'docker' on the system.")
            self._client = DockerClient
        else:
            raise ExecutorException(f"Unknown container client '{self._container_client}'.")

        with self.get_client() as client:
            try:
                # Check if we have the image locally
                image = client.images.get(image_name)
                if not image:
                    # Try to pull the image
                    image = client.images.pull(image_name)
            except (PodmanError, DockerException) as e:
                raise ExecutorException(f"Cannot find {image_name}.") from e

        self.attrs = image.attrs

    @contextmanager
    def get_client(self):
        try:
            yield self._client(**self._kwargs)
        except (PodmanError, DockerException, ValueError) as e:
            raise ExecutorException(str(e)) from e

    def copy_in(self, container, source_path: Path, destination_dir: PurePath):
        src = source_path.expanduser().absolute().as_posix()
        dst = destination_dir.as_posix()

        cmd = [
            self._container_client, "cp", str(src), f"{container.id}:{dst}"
        ]
        try:
            log.debug(f"copy-in (cmd): {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
        except subprocess.SubprocessError as e:
            raise ExecutorException from e

    def copy_out(self, container, source_path: PurePath, destination_dir: Path):
        src = source_path.as_posix()
        dst = destination_dir.expanduser().absolute().as_posix()

        cmd = [
            self._container_client, "cp", f"{container.id}:{src}", dst
        ]
        try:
            log.debug(f"copy-out (cmd): {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
        except subprocess.SubprocessError as e:
            raise ExecutorException from e

    def run(self, cmd: List[str], copy_in: List[Tuple[Path, PurePath]] = None,
            copy_out: List[Tuple[PurePath, Path]] = None, environment=None,
            no_fail_copy_out=False):

        with self.get_client() as client:
            # prepare container for given image and command
            image = client.images.get(self.attrs["Id"])
            # FIXME: create a disposable container that will be removed after execution
            container = client.containers.create(
                image, cmd, privileged=True, environment=environment)
            log.info(f"Executing '{' '.join(cmd)}' in {container}...")

            # copy-in hook
            for src, dst in copy_in or []:
                self.copy_in(container, source_path=src, destination_dir=dst)

            # run container
            container.start()

            # stream output
            process = subprocess.Popen([self._container_client, "logs", "-f", container.id],
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            while True:
                if not process.stdout:
                    break
                line = process.stdout.readline()
                if process.poll() is not None:
                    break
                if line:
                    log.info(f"output: {line.decode('utf-8', errors='replace').rstrip()}")
            rc = process.poll()
            if rc != 0:
                raise ExecutorException(f"Failed to stream output (status={rc}).")

            # wait container
            status = container.wait()
            if self._container_client == "docker":
                status = status["StatusCode"]
            if status != 0:
                raise ExecutorException(f"Failed to run '{cmd}' (status={status}).")

            # copy-out hook
            for src, dst in copy_out or []:
                try:
                    self.copy_out(container, source_path=src, destination_dir=dst)
                except ExecutorException as e:
                    # Ignore copy-out failure if requested
                    if no_fail_copy_out:
                        log.warning(f"File not found inside container: {src}.")
                        continue
                    raise e
