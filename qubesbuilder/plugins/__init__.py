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
        backend_vmm: str,
    ):
        super().__init__(
            component=component,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )
        self.dist = dist
        self.backend_vmm = backend_vmm

        self._placeholders.update({"@SOURCE_DIR@": str(BUILDER_DIR / component.name)})
        self._placeholders.update({"@BACKEND_VMM@": backend_vmm})

        self.environment["BACKEND_VMM"] = backend_vmm

    def get_dist_component_artifacts_dir(self, stage: str):
        path = (
            self.artifacts_dir
            / "components"
            / self.component.name
            / f"{self.component.version}-{self.component.release}/{self.dist.distribution}"
            / stage
        )
        return path

    def get_dist_component_artifacts_dir_history(self, stage: str):
        path = (self.artifacts_dir / "components" / self.component.name).resolve()
        return list(path.glob(f"*/{self.dist.distribution}/{stage}"))

    def get_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ) -> Dict:
        artifacts_dir = artifacts_dir or self.get_dist_component_artifacts_dir(stage)
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

    def save_artifacts_info(
        self, stage: str, basename: str, info: dict, artifacts_dir: Path = None
    ):
        artifacts_dir = artifacts_dir or self.get_dist_component_artifacts_dir(stage)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(artifacts_dir / f"{basename}.{stage}.yml", "w") as f:
                f.write(yaml.safe_dump(info))
        except (PermissionError, yaml.YAMLError) as e:
            msg = f"{self.component}:{self.dist}:{basename}: Failed to write info for {stage} stage."
            raise PluginError(msg) from e

    def delete_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ):
        artifacts_dir = artifacts_dir or self.get_dist_component_artifacts_dir(stage)
        info_path = artifacts_dir / f"{basename}.{stage}.yml"
        if info_path.exists():
            info_path.unlink()


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
        backend_vmm: str,
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
            backend_vmm=backend_vmm,
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
        backend_vmm: str,
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
            backend_vmm=backend_vmm,
        )

        # Per distribution (e.g. vm-bookworm) overrides per package set (e.g. vm)
        parameters = self.component.get_parameters(self._placeholders)

        self.parameters.update(parameters.get(self.dist.package_set, {}).get("deb", {}))
        self.parameters.update(
            parameters.get(self.dist.distribution, {}).get("deb", {})
        )
