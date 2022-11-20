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

import hashlib
import re
import subprocess
from _sha512 import sha512
from pathlib import Path
from typing import Union, List

import pathspec
import yaml
from packaging.version import Version, InvalidVersion

from qubesbuilder.common import sanitize_line, deep_check, VerificationMode
from qubesbuilder.exc import ComponentError, NoQubesBuilderFileError


class QubesVersion(Version):
    """Version class that preserves '-' in X.Y-rcZ version"""

    def __init__(self, version: str) -> None:
        super().__init__(version)
        if "-rc" in version:
            # pylint: disable=protected-access
            self._version = self._version._replace(pre=("-rc", self._version.pre[1]))  # type: ignore


class QubesComponent:
    def __init__(
        self,
        source_dir: Union[str, Path],
        name: str = None,
        url: str = None,
        branch: str = "master",
        verification_mode: VerificationMode = VerificationMode.SignedCommit,
        maintainers: List = None,
        timeout: int = None,
        fetch_versions_only: bool = False,
        devel_path: Path = None,
    ):
        self.source_dir: Path = (
            Path(source_dir) if isinstance(source_dir, str) else source_dir
        )
        self.name: str = name or self.source_dir.name
        self.version = ""
        self.release = ""
        self.devel = ""
        self.url = url or f"https://github.com/QubesOS/qubes-{self.name}"
        self.branch = branch
        self.maintainers = maintainers or []
        self.verification_mode = verification_mode
        self.timeout = timeout
        self.fetch_versions_only = fetch_versions_only
        self._source_hash = ""
        self._devel_path = devel_path

    @property
    def verrel(self):
        nvr = f"{self.version}-{self.release}"
        if self.devel:
            nvr = f"{nvr}.{self.devel}"
        return nvr

    def increment_devel_versions(self):
        devel = "1"
        if not self._devel_path:
            raise ComponentError(f"Devel path not provided for {self.name}.")
        self._devel_path.parent.mkdir(parents=True, exist_ok=True)
        if self._devel_path.exists():
            try:
                with open(self._devel_path) as fd:
                    devel = fd.read().split("\n")[0]
                assert re.fullmatch(r"[0-9]+", devel)
                devel = str(int(devel) + 1)
            except AssertionError as e:
                raise ComponentError(f"Invalid devel version for {self.name}.") from e
        self._devel_path.write_text(devel)
        self.devel = devel

    def get_parameters(self, placeholders: dict = None):
        if not self.source_dir.exists():
            raise ComponentError(f"Cannot find source directory {self.source_dir}.")

        version = ""
        release = ""
        devel = ""

        version_file = self.source_dir / "version"
        if version_file.exists():
            try:
                with open(version_file) as fd:
                    version = str(QubesVersion(fd.read().split("\n")[0]))
            except InvalidVersion as e:
                raise ComponentError(f"Invalid version for {self.source_dir}.") from e
        else:
            result = subprocess.run(
                "git describe --match='v*' --abbrev=0",
                capture_output=True,
                shell=True,
                cwd=self.source_dir,
            )
            if result.stdout:
                version = sanitize_line(result.stdout.rstrip(b"\n")).rstrip()
                version_re = re.compile(r"v?([0-9]+(?:\.[0-9]+)*)-([0-9]+.*)")
                if len(version) > 255 or not version_re.match(version):
                    raise ComponentError(f"Invalid version for {self.source_dir}.")
                version, release = version_re.match(version).groups()  # type: ignore

        if not version:
            raise ComponentError(f"Cannot determine version for {self.source_dir}.")

        release_file = self.source_dir / "rel"
        if not release:
            if not release_file.exists():
                release = "1"
            else:
                try:
                    with open(release_file) as fd:
                        release = fd.read().split("\n")[0]
                    Version(f"{version}-{release}")
                except (InvalidVersion, AssertionError) as e:
                    raise ComponentError(
                        f"Invalid release for {self.source_dir}."
                    ) from e

        if self._devel_path and self._devel_path.exists():
            try:
                with open(self._devel_path) as fd:
                    devel = fd.read().split("\n")[0]
                assert re.fullmatch(r"[0-9]+", devel)
            except AssertionError as e:
                raise ComponentError(f"Invalid devel version for {self.name}.") from e

        self.version = version
        self.release = release
        self.devel = devel

        build_file = self.source_dir / ".qubesbuilder"
        if not build_file.exists():
            raise NoQubesBuilderFileError(
                f"Cannot find '.qubesbuilder' in {self.source_dir}."
            )

        with open(build_file) as f:
            data = f.read()

        if not placeholders:
            placeholders = {}
        placeholders.update({"@VERSION@": self.version, "@REL@": self.release})

        for key, val in placeholders.items():
            data = data.replace(key, str(val))

        try:
            rendered_data = yaml.safe_load(data) or {}
        except yaml.YAMLError as e:
            raise ComponentError(f"Cannot render '.qubesbuilder'.") from e

        # TODO: add more extra validation of some field
        try:
            deep_check(rendered_data)
        except ValueError as e:
            raise ComponentError(f"Invalid '.qubesbuilder': {str(e)}")

        return rendered_data

    @staticmethod
    def _update_hash_from_file(filename: Path, hash: sha512):
        with open(str(filename), "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash.update(chunk)
        return hash

    def _update_hash_from_dir(self, directory: Path, hash: sha512):
        if not directory.exists() or not directory.is_dir():
            raise ComponentError(f"Cannot find '{directory}'.")
        paths = [name for name in Path(directory).iterdir()]
        excluded_paths = [directory / ".git"]
        # We ignore .git and content defined by .gitignore
        if (directory / ".gitignore").exists():
            lines = (directory / ".gitignore").read_text().splitlines()
            spec = pathspec.PathSpec.from_lines("gitwildmatch", lines)
            excluded_paths += [name for name in paths if spec.match_file(str(name))]
        sorted_paths = [path for path in paths if path not in excluded_paths]
        # We ensure to compute hash always in a sorted order
        sorted_paths = sorted(sorted_paths, key=lambda p: str(p).lower())
        for path in sorted_paths:
            hash.update(path.name.encode())
            if path.is_file():
                hash = self._update_hash_from_file(path, hash)
            elif path.is_dir():
                hash = self._update_hash_from_dir(path, hash)
        return hash

    def get_source_hash(self, force_update=True):
        if not self._source_hash or force_update:
            source_dir_hash = self._update_hash_from_dir(
                self.source_dir, hashlib.sha512()
            ).hexdigest()
            self._source_hash = str(source_dir_hash)
        return self._source_hash

    def get_source_commit_hash(self):
        cmd = ["git", "-C", str(self.source_dir), "rev-parse", "HEAD^{}"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip("\n")
        except subprocess.CalledProcessError as e:
            raise ComponentError(
                f"Cannot determine source commit hash for {self.source_dir}."
            ) from e

    def is_salt(self):
        return (self.source_dir / "FORMULA").exists()

    def to_str(self) -> str:
        return self.source_dir.name

    def __repr__(self):
        return f"<QubesComponent {self.to_str()}>"

    def __eq__(self, other):
        return repr(self) == repr(other)

    def __str__(self):
        return self.to_str()
