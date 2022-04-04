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
import pathspec
from _sha1 import sha1
from pathlib import Path
from typing import Union, List

import yaml
from packaging.version import Version, InvalidVersion

from qubesbuilder.exc import ComponentError


class QubesComponent:
    def __init__(
        self,
        source_dir: Union[str, Path],
        name: str = None,
        url: str = None,
        branch: str = "master",
        insecure_skip_checking: bool = False,
        less_secure_signed_commits_sufficient: bool = False,
        maintainers: List = None,
    ):
        self.source_dir: Path = (
            Path(source_dir) if isinstance(source_dir, str) else source_dir
        )
        self.name: str = name or self.source_dir.name
        self.version = ""
        self.release = ""
        self.url = url or f"https://github.com/QubesOS/qubes-{self.name}"
        self.branch = branch
        self.maintainers = maintainers or []
        self.insecure_skip_checking = insecure_skip_checking
        self.less_secure_signed_commits_sufficient = (
            less_secure_signed_commits_sufficient
        )
        self._source_hash = ""

    def get_parameters(self, placeholders: dict = None):
        if not self.source_dir.exists():
            raise ComponentError(f"Cannot find source directory {self.source_dir}")

        version_file = self.source_dir / "version"
        if not version_file.exists():
            raise ComponentError(f"Cannot find version file in {self.source_dir}")

        try:
            with open(version_file) as fd:
                version = Version(fd.read().split("\n")[0]).base_version
        except InvalidVersion as e:
            raise ComponentError(f"Invalid version for {self.source_dir}") from e

        release_file = self.source_dir / "rel"
        if not release_file.exists():
            release = "1"
        else:
            try:
                with open(release_file) as fd:
                    release = fd.read().split("\n")[0]
                Version(f"{version}-{release}")
            except (InvalidVersion, AssertionError) as e:
                raise ComponentError(f"Invalid release for {self.source_dir}") from e

        self.version = version
        self.release = release

        build_file = self.source_dir / ".qubesbuilder"
        if not build_file.exists():
            raise ComponentError(f"Cannot find '.qubesbuilder' in {self.source_dir}")

        with open(build_file) as f:
            data = f.read()

        if not placeholders:
            placeholders = {}
        placeholders.update({"@VERSION@": self.version, "@REL@": self.release})

        for key, val in placeholders.items():
            data = data.replace(key, val)

        try:
            rendered_data = yaml.safe_load(data)
        except yaml.YAMLError as e:
            raise ComponentError(f"Cannot render '.qubesbuilder'.") from e

        return rendered_data or {}

    @staticmethod
    def _update_hash_from_file(filename: Path, hash: sha1):
        with open(str(filename), "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash.update(chunk)
        return hash

    def _update_hash_from_dir(self, directory: Path, hash: sha1):
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

    def get_source_hash(self):
        if not self._source_hash:
            source_dir_hash = self._update_hash_from_dir(
                self.source_dir, hashlib.sha1()
            ).hexdigest()
            self._source_hash = str(source_dir_hash)
        return self._source_hash

    def to_str(self) -> str:
        return self.source_dir.name

    def __repr__(self):
        return f"<QubesComponent {self.to_str()}>"

    def __eq__(self, other):
        return repr(self) == repr(other)

    def __str__(self):
        return self.to_str()
