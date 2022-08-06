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

from pathlib import Path, PurePosixPath
from typing import List, Dict

import dateutil.parser
import yaml
from dateutil.parser import parse as parsedate

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.template import QubesTemplate

# Directories inside executor
BUILDER_DIR = Path("/builder")
BUILD_DIR = BUILDER_DIR / "build"
PLUGINS_DIR = BUILDER_DIR / "plugins"
DISTFILES_DIR = BUILDER_DIR / "distfiles"
REPOSITORY_DIR = BUILDER_DIR / "repository"
CACHE_DIR = BUILDER_DIR / "cache"


class PackagePath(PurePosixPath):
    def mangle(self):
        return str(self).replace("/", "_")


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
            self.environment["VERBOSE"] = "1"
        if self.debug:
            self.environment["DEBUG"] = "1"

    def before(self, stage: str):
        pass

    def run(self, stage: str):
        pass

    def after(self, stage: str):
        pass

    def update_parameters(self):
        pass

    def get_temp_dir(self):
        path = self.artifacts_dir / "tmp"
        return path.resolve()

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

    @staticmethod
    def get_artifacts_info_filename(stage: str, basename: str):
        return f"{basename}.{stage}.yml"

    def get_component_distfiles_dir(self):
        path = self.get_distfiles_dir() / self.component.name
        return path

    def get_component_artifacts_dir(self, stage: str):
        path = self.artifacts_dir / "components" / self.component.name
        path = path / f"{self.component.version}-{self.component.release}"
        path = path / "nodist" / stage
        return path.resolve()

    def get_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ) -> Dict:
        artifacts_dir = artifacts_dir or self.get_component_artifacts_dir(stage)
        fileinfo = artifacts_dir / self.get_artifacts_info_filename(stage, basename)
        if fileinfo.exists():
            try:
                with open(fileinfo, "r") as f:
                    artifacts_info = yaml.safe_load(f.read())
                return artifacts_info or {}
            except (PermissionError, yaml.YAMLError) as e:
                msg = f"{self.component}:{basename}: Failed to read info from {stage} stage."
                raise PluginError(msg) from e
        return {}

    def save_artifacts_info(
        self, stage: str, basename: str, info: dict, artifacts_dir: Path = None
    ):
        artifacts_dir = artifacts_dir or self.get_component_artifacts_dir(stage)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(
                artifacts_dir / self.get_artifacts_info_filename(stage, basename), "w"
            ) as f:
                f.write(yaml.safe_dump(info))
        except (PermissionError, yaml.YAMLError) as e:
            msg = (
                f"{self.component}:{basename}: Failed to write info for {stage} stage."
            )
            raise PluginError(msg) from e

    def delete_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ):
        artifacts_dir = artifacts_dir or self.get_component_artifacts_dir(stage)
        info_path = artifacts_dir / self.get_artifacts_info_filename(stage, basename)
        if info_path.exists():
            info_path.unlink()

    def check_stage_artifacts(self, stage: str, artifacts_dir: Path = None):
        for build in self.parameters.get("build", []):
            build_bn = build.mangle()
            if not self.get_artifacts_info(
                stage=stage, basename=build_bn, artifacts_dir=artifacts_dir
            ):
                msg = f"Missing '{stage}' stage artifacts for {build_bn}!"
                raise PluginError(msg)


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

        # Per distribution (e.g. host-fc42) overrides per package set (e.g. host)
        parameters = self.component.get_parameters(self._placeholders)

        self.parameters.update(
            parameters.get(self.dist.package_set, {}).get(self.dist.type, {})
        )
        self.parameters.update(
            parameters.get(self.dist.distribution, {}).get(self.dist.type, {})
        )

        self.parameters["build"] = [
            PackagePath(build) for build in self.parameters.get("build", [])
        ]
        # For retro-compatibility
        if self.dist.type == "rpm":
            self.parameters["build"] += [
                PackagePath(spec) for spec in self.parameters.get("spec", [])
            ]
        # Check conflicts when mangle paths
        mangle_builds = [build.mangle() for build in self.parameters.get("build", [])]
        if len(set(mangle_builds)) != len(self.parameters["build"]):
            raise PluginError(f"{component}:{dist}: Conflicting build paths")

    def get_dist_component_artifacts_dir_history(self, stage: str):
        path = (self.artifacts_dir / "components" / self.component.name).resolve()
        return list(path.glob(f"*/{self.dist.distribution}/{stage}"))

    def get_dist_component_artifacts_dir(self, stage: str):
        path = self.artifacts_dir / "components" / self.component.name
        path = path / f"{self.component.version}-{self.component.release}"
        path = path / self.dist.distribution / stage
        return path.resolve()

    def get_dist_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ) -> Dict:
        return self.get_artifacts_info(
            stage=stage,
            basename=basename,
            artifacts_dir=artifacts_dir or self.get_dist_component_artifacts_dir(stage),
        )

    def save_dist_artifacts_info(
        self, stage: str, basename: str, info: dict, artifacts_dir: Path = None
    ):
        return self.save_artifacts_info(
            stage=stage,
            basename=basename,
            artifacts_dir=artifacts_dir or self.get_dist_component_artifacts_dir(stage),
            info=info,
        )

    def delete_dist_artifacts_info(
        self, stage: str, basename: str, artifacts_dir: Path = None
    ):
        return self.delete_artifacts_info(
            stage=stage,
            basename=basename,
            artifacts_dir=artifacts_dir or self.get_dist_component_artifacts_dir(stage),
        )

    def check_dist_stage_artifacts(self, stage: str, artifacts_dir: Path = None):
        return self.check_stage_artifacts(
            stage=stage,
            artifacts_dir=artifacts_dir or self.get_dist_component_artifacts_dir(stage),
        )


class TemplatePlugin(Plugin):
    def __init__(
        self,
        template: QubesTemplate,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )
        self.dist = template.distribution
        self.template = template

    def get_artifacts_info(self, stage: str) -> Dict:
        fileinfo = self.get_templates_dir() / f"{self.template.name}.{stage}.yml"
        if fileinfo.exists():
            try:
                with open(fileinfo, "r") as f:
                    artifacts_info = yaml.safe_load(f.read())
                return artifacts_info or {}
            except (PermissionError, yaml.YAMLError) as e:
                msg = f"{self.template}: Failed to read info from {stage} stage."
                raise PluginError(msg) from e
        return {}

    def save_artifacts_info(self, stage: str, info: dict):
        artifacts_dir = self.get_templates_dir()
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        try:
            with open(artifacts_dir / f"{self.template}.{stage}.yml", "w") as f:
                f.write(yaml.safe_dump(info))
        except (PermissionError, yaml.YAMLError) as e:
            msg = f"{self.template}: Failed to write info for {stage} stage."
            raise PluginError(msg) from e

    def delete_artifacts_info(self, stage: str):
        artifacts_dir = self.get_templates_dir()
        info_path = artifacts_dir / f"{self.template}.{stage}.yml"
        if info_path.exists():
            info_path.unlink()

    def get_template_timestamp(self) -> str:
        if not self.template.timestamp:
            # Read information from build stage
            if not (
                self.get_templates_dir() / f"build_timestamp_{self.template.name}"
            ).exists():
                raise PluginError(f"{self.template}: Cannot find build timestamp.")
            with open(
                self.get_templates_dir() / f"build_timestamp_{self.template.name}"
            ) as f:
                data = f.read().splitlines()

            try:
                self.template.timestamp = parsedate(data[0]).strftime("%Y%m%d%H%M")
            except (dateutil.parser.ParserError, IndexError) as e:
                msg = f"{self.template}: Failed to parse build timestamp format."
                raise PluginError(msg) from e
        return self.template.timestamp
