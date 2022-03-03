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

from pathlib import Path, PurePath
from typing import List

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


class BasePlugin:
    """
    Base plugin
    """

    plugin_dependencies: List[str] = []

    def __init__(
        self,
        dist: QubesDistribution,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool,
        debug: bool,
    ):
        self.dist = dist
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

        # Legacy values
        self.environment = {
            "DIST": self.dist.name,
            "DISTRIBUTION": self.dist.fullname
        }
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


class Plugin(BasePlugin):
    """
    Plugin for components
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
            dist=dist,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )
        self.component = component

        self._placeholders.update({"@SOURCE_DIR@": str(BUILDER_DIR / component.name)})

    def get_component_dir(self, stage: str):
        path = self.artifacts_dir / "components" / self.component.name
        path = (
            path
            / f"{self.component.version}-{self.component.release}/{self.dist.distribution}"
        )
        path = path / stage
        return path.resolve()
