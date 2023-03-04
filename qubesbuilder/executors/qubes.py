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
import os
import re
import shutil
import subprocess
from pathlib import Path, PurePath
from typing import List, Tuple, Union

from qubesbuilder.common import sanitize_line, str_to_bool
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger

_qubes_re: re.Pattern[bytes] = re.compile(br'[^a-zA-Z0-9_.]')
_qube_name_re: re.Pattern[bytes] = re.compile(br'\A(?:@dispvm:)?[a-zA-Z][a-zA-Z0-9_-]{0,30}\Z')
log = get_logger("executor:qubes")

def _encode_for_vmexec(args: List[bytes], destination_vm: bytes,
                       disposable: bool) -> List[bytes]:
    """
    Encode an argument list for qubes.VMExec call.
    """

    _sub = re.sub
    assert destination_vm.match(_qube_name_re), f'Invalid qube name {destination_vm!r}'
    def encode(part: re.Match[bytes]) -> bytes:
        g = part.group(0)
        return b'--' if g == b'-' else b'-%02X' % ord(g)

    out: List[bytes] = [b'qubes.VMExec']
    for arg in args:
        assert b'\0' not in arg, "NUL not allowed in command line argument"
        out.append(_sub(_qubes_re, encode, arg))
    out_bytes = b'+'.join(out)
    return [
        b'/usr/lib/qubes/qrexec-client-vm',
        b'--filter-escape-chars-stderr',
        b'--filter-escape-chars-stdout',
        b'--',
        destination_vm
        out_bytes,
    ]

def _encode_shell_command_list(argument_lists: List[List[str]]) -> str:
    return '&&'.join(' '.join(shlex.quote(arg) for arg in args)
                     for args in argument_lists)

class QubesExecutor(Executor):
    def __init__(self, dispvm, clean: Union[str, bool] = True, **kwargs):
        # FIXME: dispvm is the template used for creating a disposable qube.
        #  It is currently unused and need to be specified when calling qrexec
        self._dispvm = dispvm
        self._clean = clean if isinstance(clean, bool) else str_to_bool(clean)
        self._kwargs = kwargs

    def get_user(self):
        return "user"

    def get_group(self):
        return "user"

    def copy_in(self, vm: str, source_path: Path, destination_dir: PurePath):  # type: ignore
        src = source_path.expanduser().resolve()
        dst = destination_dir
        builder_dir = self.get_builder_dir()
        delete_command = ['rm', '-rf', '--', builder_dir / 'incoming' / src.name, dst.as_posix() / src.name]
        mkdir_command = ['mkdir', '-p', '--', dst.as_posix()]
        mv_command = ['mv', '--', builder_dir / 'incoming' / src.name, dst.as_posix()]
        bash_command = [
            b'bash',
            b'-euc',
            _encode_shell_command_list([mkdir_command, mv_command]).encode('utf-8', 'surrogateescape'),
        ])
        # FIXME: Refactor the qvm-run and qrexec commandlines.
        vm_bytes = vm.encode('ascii', 'strict')
        prepare_incoming_and_destination = _encode_for_vmexec(delete_command, vm_bytes)
        copy_to_incoming = [
            b"/usr/lib/qubes/qrexec-client-vm",
            b"--filter-escape-chars-stderr",
            b"--filter-escape-chars-stdout",
            b"--",
            vm_bytes,
            b"qubesbuilder.FileCopyIn",
            b"/usr/lib/qubes/qfile-agent",
            str(src).encode('utf-8', 'surrogateescape'),
        ]
        move_to_destination = _encode_for_vmexec(bash_command, vm_bytes)
        try:
            log.debug(f"copy-in (cmd): {' '.join(prepare_incoming_and_destination)}")
            subprocess.run(prepare_incoming_and_destination, check=True)

            log.debug(f"copy-in (cmd): {' '.join(copy_to_incoming)}")
            subprocess.run(copy_to_incoming, check=True)

            log.debug(f"copy-in (cmd): {' '.join(move_to_destination)}")
            subprocess.run(move_to_destination, check=True)
        except subprocess.CalledProcessError as e:
            if e.stderr is not None:
                msg = sanitize_line(e.stderr.rstrip(b"\n")).rstrip()
                log.error(msg)
            raise ExecutorError from e

    def copy_out(self, vm, source_path: PurePath, destination_dir: Path, dig_holes=False):  # type: ignore
        src = source_path
        dst = destination_dir.resolve()

        # Remove local file or directory if exists
        dst_path = dst / src.name
        if os.path.exists(dst_path):
            if dst_path.is_dir():
                shutil.rmtree(dst / src.name)
            else:
                os.remove(dst_path)

        dst.mkdir(parents=True, exist_ok=True)

        cmd = [
            "/usr/lib/qubes/qrexec-client-vm",
            "--filter-escape-chars-stderr",
            "--filter-escape-chars-stdout",
            vm,
            f"qubesbuilder.FileCopyOut+{str(src).replace('/', '__')}",
            "/usr/lib/qubes/qfile-unpacker",
            str(os.getuid()),
            str(dst),
        ]
        try:
            log.debug(f"copy-out (cmd): {' '.join(cmd)}")
            subprocess.run(cmd, check=True)

            if dig_holes and not dst_path.is_dir():
                log.debug("copy-out (detect zeroes and replace with holes)")
                subprocess.run(["/usr/bin/fallocate", "-d", str(dst_path)], check=True)
        except subprocess.CalledProcessError as e:
            if e.stderr is not None:
                msg = sanitize_line(e.stderr.rstrip(b"\n")).rstrip()
                log.error(msg)
            raise ExecutorError from e

    def run(  # type: ignore
        self,
        cmd: List[str],
        copy_in: List[Tuple[Path, PurePath]] = None,
        copy_out: List[Tuple[PurePath, Path]] = None,
        files_inside_executor_with_placeholders: List[Path] = None,
        environment: dict = None,
        no_fail_copy_out_allowed_patterns=None,
        dig_holes: bool = False,
    ):

        dispvm = None
        try:
            result = subprocess.run(
                ["qrexec-client-vm", "dom0", "admin.vm.CreateDisposable"],
                capture_output=True,
                stdin=subprocess.DEVNULL,
            )
            dispvm = result.stdout.decode("utf8").replace("0\x00", "")
            if not re.match(r"disp[0-9]{1,4}", dispvm):
                raise ExecutorError("Failed to create disposable qube.")

            # Adjust log namespace
            log.name = f"executor:qubes:{dispvm}"

            # Start the DispVM by running creation of builder directory
            start_cmd = [
                "/usr/bin/qvm-run-vm",
                dispvm,
                f"bash -c 'sudo mkdir -p {self.get_builder_dir()} {self.get_builder_dir()} "
                f"{self.get_builder_dir()/'build'} {self.get_builder_dir()/'plugins'} "
                f"{self.get_builder_dir()/'distfiles'} "
                f"&& sudo chown -R {self.get_user()}:{self.get_group()} {self.get_builder_dir()}'",
            ]
            subprocess.run(start_cmd, stdin=subprocess.DEVNULL)

            # copy-in hook
            for src_in, dst_in in copy_in or []:
                self.copy_in(dispvm, source_path=src_in, destination_dir=dst_in)

            # replace placeholders
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
                if sed_cmd:
                    sed_cmd = [c.replace("'", "'\\''") for c in sed_cmd]
                    sed_cmd = [
                        "/usr/bin/qvm-run-vm",
                        dispvm,
                        f'bash -c \'{" && ".join(sed_cmd)}\'',
                    ]
                    subprocess.run(sed_cmd, stdin=subprocess.DEVNULL)

            bash_env = []
            if environment:
                for key, val in environment.items():
                    bash_env.append(f"{str(key)}='{str(val)}'")

            cmd = [c.replace("'", "'\\''") for c in cmd]
            qvm_run_cmd = [
                "/usr/bin/qvm-run-vm",
                dispvm,
                f'env {" ".join(bash_env)} bash -c \'{" && ".join(cmd)}\'',
            ]

            log.info(f"Executing '{' '.join(qvm_run_cmd)}'.")

            # stream output for command
            process = subprocess.Popen(
                qvm_run_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT
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
                raise ExecutorError(
                    f"Failed to run '{' '.join(qvm_run_cmd)}' (status={rc})."
                )

            # copy-out hook
            for src_out, dst_out in copy_out or []:
                try:
                    self.copy_out(
                        dispvm,
                        source_path=src_out,
                        destination_dir=dst_out,
                        dig_holes=dig_holes,
                    )
                except ExecutorError as e:
                    # Ignore copy-out failure if requested
                    if isinstance(no_fail_copy_out_allowed_patterns, list) and any(
                        [p in src_out.name for p in no_fail_copy_out_allowed_patterns]
                    ):
                        log.warning(f"File not found inside container: {src_out}.")
                        continue
                    raise e
        finally:
            # Kill the DispVM to prevent hanging for while
            if dispvm and self._clean:
                subprocess.run(
                    ["qrexec-client-vm", dispvm, "admin.vm.Kill"],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                )
