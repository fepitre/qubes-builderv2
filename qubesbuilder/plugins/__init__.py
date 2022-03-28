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

import yaml
import hashlib
from _sha1 import sha1
from pathlib import Path
from pathlib import PurePath
from typing import List, Dict

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution

# Directories inside executor
BUILDER_DIR = PurePath("/builder")
BUILD_DIR = BUILDER_DIR / "build"
PLUGINS_DIR = BUILDER_DIR / "plugins"
DISTFILES_DIR = BUILDER_DIR / "distfiles"
REPOSITORY_DIR = BUILDER_DIR / "repository"
CACHE_DIR = BUILDER_DIR / "cache"


class PluginError(Exception):
    """
    Base plugin exception
    """

    pass


class Plugin:
    """
    Generic plugin
    """

    plugin_dependencies: List[str] = []

    def __init__(
        self,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool,
        debug: bool,
    ):
        self.plugins_dir = plugins_dir
        self.artifacts_dir = artifacts_dir
        self.verbose = verbose
        self.debug = debug

        # Plugin parameters
        self.parameters: dict = {}

        # Default placeholders
        self._placeholders = {
            "@BUILDER_DIR@": str(BUILDER_DIR),
            "@BUILD_DIR@": str(BUILD_DIR),
            "@PLUGINS_DIR@": str(PLUGINS_DIR),
            "@DISTFILES_DIR@": str(DISTFILES_DIR),
        }

        self.environment = {}
        if self.verbose:
            self.environment["VERBOSE"] = 1
        if self.debug:
            self.environment["DEBUG"] = 1

    def run(self, stage: str):
        pass

    def update_parameters(self):
        pass

    def get_sources_dir(self):
        path = self.artifacts_dir / "sources"
        return path.resolve()

    def get_repository_dir(self):
        path = self.artifacts_dir / "repository"
        return path.resolve()

    def get_repository_publish_dir(self):
        path = self.artifacts_dir / "repository-publish"
        return path.resolve()

    def get_distfiles_dir(self):
        path = self.artifacts_dir / "distfiles"
        return path.resolve()

    def get_templates_dir(self):
        path = self.artifacts_dir / "templates"
        return path.resolve()


class ComponentPlugin(Plugin):
    """
    Component plugin
    """

    plugin_dependencies: List[str] = []

    def __init__(
        self,
        component: QubesComponent,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool,
        debug: bool,
    ):
        super().__init__(
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )
        self.component = component
        self._placeholders.update({"@SOURCE_DIR@": str(BUILDER_DIR / component.name)})
        self._source_hash = ""

    def get_component_dir(self, stage: str):
        path = self.artifacts_dir / "components" / self.component.name
        path = path / f"{self.component.version}-{self.component.release}"
        path = path / stage
        return path.resolve()

    @staticmethod
    def _update_hash_from_file(filename: Path, hash: sha1):
        with open(str(filename), "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash.update(chunk)
        return hash

    def _update_hash_from_dir(self, directory: Path, hash: sha1):
        if not directory.exists() or not directory.is_dir():
            raise PluginError(f"Cannot find '{directory}'.")
        # We ensure to compute hash always in a sorted order
        sorted_paths = sorted(Path(directory).iterdir(), key=lambda p: str(p).lower())
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
                self.get_sources_dir() / self.component.name, hashlib.sha1()
            ).hexdigest()
            self._source_hash = str(source_dir_hash)
        return self._source_hash


class DistributionPlugin(ComponentPlugin):
    """
    Distribution Component plugin
    """

    plugin_dependencies: List[str] = []

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool,
        debug: bool,
    ):
        super().__init__(
            component=component,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )
        self.dist = dist
        self._placeholders.update({"@SOURCE_DIR@": str(BUILDER_DIR / component.name)})

    def get_dist_component_artifacts_dir(self, stage: str):
        path = self.artifacts_dir / "components" / self.component.name
        path = (
            path
            / f"{self.component.version}-{self.component.release}/{self.dist.distribution}"
        )
        path = path / stage
        return path.resolve()

    def get_artifacts_info(self, stage: str, basename: str) -> Dict:
        artifacts_dir = self.get_dist_component_artifacts_dir(stage)
        fileinfo = artifacts_dir / f"{basename}.{stage}.yml"
        if fileinfo.exists():
            try:
                with open(fileinfo, "r") as f:
                    artifacts_info = yaml.safe_load(f.read())
                return artifacts_info or {}
            except (PermissionError, yaml.YAMLError) as e:
                msg = f"{self.component}:{self.dist}:{basename}: Failed to read info from {stage} stage."
                raise PluginError(msg) from e
        return {}

    def save_artifacts_info(self, stage: str, basename: str, info: dict):
        artifacts_dir = self.get_dist_component_artifacts_dir(stage=stage)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(artifacts_dir / f"{basename}.{stage}.yml", "w") as f:
                f.write(yaml.safe_dump(info))
        except (PermissionError, yaml.YAMLError) as e:
            msg = f"{self.component}:{self.dist}:{basename}: Failed to write info for {stage} stage."
            raise PluginError(msg) from e


class RPMDistributionPlugin(DistributionPlugin):

    """
    RPM distribution component plugin
    """

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool,
        debug: bool,
    ):
        super().__init__(
            component=component,
            dist=dist,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )

        # Per distribution (e.g. host-fc42) overrides per package set (e.g. host)
        parameters = self.component.get_parameters(self._placeholders)

        self.parameters.update(parameters.get(self.dist.package_set, {}).get("rpm", {}))
        self.parameters.update(
            parameters.get(self.dist.distribution, {}).get("rpm", {})
        )

        self.parameters["spec"] = [
            PurePath(spec) for spec in self.parameters.get("spec", [])
        ]


class DEBDistributionPlugin(DistributionPlugin):

    """
    RPM distribution component plugin
    """

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool,
        debug: bool,
    ):
        super().__init__(
            component=component,
            dist=dist,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )

        # Per distribution (e.g. vm-bookworm) overrides per package set (e.g. vm)
        parameters = self.component.get_parameters(self._placeholders)

        self.parameters.update(parameters.get(self.dist.package_set, {}).get("deb", {}))
        self.parameters.update(
            parameters.get(self.dist.distribution, {}).get("deb", {})
        )
