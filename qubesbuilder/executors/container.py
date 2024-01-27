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
import tempfile
from typing import List, Tuple, Union
from shlex import quote

from qubesbuilder.common import sanitize_line, str_to_bool
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger

log = get_logger("executor:container")

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
    def __init__(
        self,
        container_client,
        image,
        clean: Union[str, bool] = True,
        user: str = "user",
        group: str = "user",
        **kwargs,
    ):
        self._container_client = container_client
        self._clean = clean if isinstance(clean, bool) else str_to_bool(clean)
        self._user = user
        self._group = group
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
                docker_image = client.images.get(image)
            except (PodmanError, DockerException) as e:
                # Try to pull the image
                try:
                    docker_image = client.images.pull(image)
                except (PodmanError, DockerException) as e:
                    raise ExecutorError(f"Cannot find {image}.") from e

        self.attrs = docker_image.attrs

    def get_builder_dir(self):
        return PurePath("/builder")

    @contextmanager
    def get_client(self):
        try:
            yield self._client(**self._kwargs)
        except (PodmanError, DockerException, ValueError) as e:
            raise ExecutorError("Cannot connect to container client.") from e

    def get_user(self):
        return self._user

    def get_group(self):
        return self._group

    def copy_in(self, container, source_path: Path, destination_dir: PurePath):  # type: ignore
        src = source_path.resolve()
        dst = destination_dir.as_posix()

        try:
            # docker doesn't create parent target dirs on copy (similar to `cp`), do that first
            with tempfile.TemporaryDirectory() as empty_dir:
                for parent in list(reversed(destination_dir.parents)) + [
                    destination_dir
                ]:
                    cmd = [
                        self._container_client,
                        "cp",
                        f"{empty_dir!s}/.",
                        f"{container.id}:{parent}",
                    ]
                    log.debug(f"copy-in (cmd): {' '.join(cmd)}")
                    subprocess.run(cmd, check=True, capture_output=True)
            cmd = [self._container_client, "cp", str(src), f"{container.id}:{dst}"]
            log.debug(f"copy-in (cmd): {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            if e.stderr is not None:
                msg = (
                    sanitize_line(e.stderr.rstrip(b"\n"))
                    .rstrip()
                    .replace("Error: ", "")
                )
                log.error(msg)
            raise ExecutorError from e

    def copy_out(self, container, source_path: PurePath, destination_dir: Path):  # type: ignore
        src = source_path.as_posix()
        dst = destination_dir.resolve()

        cmd = [self._container_client, "cp", f"{container.id}:{src}", str(dst)]
        try:
            log.debug(f"copy-out (cmd): {' '.join(cmd)}")
            dst.mkdir(parents=True, exist_ok=True)
            subprocess.run(cmd, check=True, capture_output=True)
        except subprocess.CalledProcessError as e:
            if e.stderr is not None:
                msg = (
                    sanitize_line(e.stderr.rstrip(b"\n"))
                    .rstrip()
                    .replace("Error: ", "")
                )
                log.error(msg)
            raise ExecutorError from e

    def run(  # type: ignore
        self,
        cmd: List[str],
        copy_in: List[Tuple[Path, PurePath]] = None,
        copy_out: List[Tuple[PurePath, Path]] = None,
        files_inside_executor_with_placeholders: List[Union[Path, str]] = None,
        environment=None,
        no_fail_copy_out_allowed_patterns=None,
        **kwargs,
    ):

        container = None

        try:
            with self.get_client() as client:
                # prepare container for given image and command
                image = client.images.get(self.attrs["Id"])

                # fix permissions and user group
                permissions_cmd = [
                    f"sudo mkdir -p -- {quote(str(self.get_builder_dir()))} {quote(str(self.get_builder_dir()/'build'))} {quote(str(self.get_builder_dir()/'plugins'))} {quote(str(self.get_builder_dir()/'distfiles'))}",
                    f"sudo chown -R -- {quote(self._user)}:{quote(self._group)} {quote(str(self.get_builder_dir()))}",
                ]

                # replace placeholders
                sed_cmd = []
                if files_inside_executor_with_placeholders and isinstance(
                    files_inside_executor_with_placeholders, list
                ):
                    files = [
                        self.replace_placeholders(str(f))
                        for f in files_inside_executor_with_placeholders
                    ]
                    sed_cmd = [
                        f"sed -i 's#@BUILDER_DIR@#{self.get_builder_dir()}#g' {' '.join(files)}"
                    ]

                final_cmd = "&&".join(permissions_cmd + sed_cmd + cmd)
                container_cmd = ["bash", "-c", final_cmd]

                # FIXME: Ensure podman client can parse non str value
                #  https://github.com/containers/podman/issues/11984
                if self._container_client == "podman":
                    for k, v in environment.copy().items():
                        environment[k] = str(v)
                mounts = [
                    {
                        "type": "bind",
                        "source": "/dev/loop-control",
                        "target": "/dev/loop-control",
                    },
                ]
                container = client.containers.create(
                    image,
                    container_cmd,
                    privileged=True,
                    environment=environment,
                    mounts=mounts,
                )

                # Adjust log namespace
                log.name = f"executor:{self._container_client}:{container.short_id}"
                log.info(f"Executing '{final_cmd}'.")

                # copy-in hook
                for src_in, dst_in in copy_in or []:
                    self.copy_in(container, source_path=src_in, destination_dir=dst_in)

                # FIXME: Use attach method when podman-py will implement.
                #  It is for starting and streaming output directly with python.
                process = subprocess.Popen(
                    [self._container_client, "start", "--attach", container.id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                )
                while True:
                    if not process.stdout:
                        log.error(f"No output!")
                        break
                    for line in process.stdout:
                        line = sanitize_line(line.rstrip(b"\n")).rstrip()
                        log.info(f"output: {str(line)}")
                    if process.poll() is not None:
                        break
                rc = process.poll()
                if rc != 0:
                    raise ExecutorError(f"Failed to run '{final_cmd}' (status={rc}).")

                # copy-out hook
                for src_out, dst_out in copy_out or []:
                    try:
                        self.copy_out(
                            container, source_path=src_out, destination_dir=dst_out
                        )
                    except ExecutorError as e:
                        # Ignore copy-out failure if requested
                        if isinstance(no_fail_copy_out_allowed_patterns, list) and any(
                            [
                                p in src_out.name
                                for p in no_fail_copy_out_allowed_patterns
                            ]
                        ):
                            log.warning(f"File not found inside container: {src_out}.")
                            continue
                        raise e
        finally:
            if container and self._clean:
                container.wait()
                container.remove()
