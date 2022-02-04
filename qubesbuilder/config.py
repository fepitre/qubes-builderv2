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

from pathlib import Path
from typing import Union, List, Dict

import yaml

from qubesbuilder.common import PROJECT_PATH
from qubesbuilder.component import Component
from qubesbuilder.dist import Dist
from qubesbuilder.exc import ConfigException
from qubesbuilder.executors.helpers import getExecutor
from qubesbuilder.log import get_logger

STAGES = ["fetch", "prep", "build", "post", "verify", "sign", "publish"]

log = get_logger("config")


class Config:

    def __init__(self, conf_file: Union[Path, str]):
        if isinstance(conf_file, str):
            conf_file = Path(conf_file).resolve()

        if not conf_file.exists():
            raise ConfigException(f"Cannot find config '{conf_file}'.")

        try:
            with open(conf_file) as f:
                self._conf = yaml.safe_load(f.read())
        except yaml.YAMLError as e:
            raise ConfigException(f"Failed to parse config '{conf_file}'.") from e

        # Qubes OS distributions
        self._dists: List = []

        # Default Qubes OS build pipeline stages
        self._stages: dict = {}

        # Qubes OS components
        self._components: List[Component] = []

        # Artifacts directory location
        if self._conf.get("artifacts-dir", None):
            self._artifacts_dir = Path(self._conf["artifacts-dir"]).resolve()
            log.debug(f"Using '{self._artifacts_dir}' as artifacts directory.")
        else:
            self._artifacts_dir = PROJECT_PATH
            log.debug(f"Using '{self._artifacts_dir}' as artifacts directory.")

        self.verbose = self._conf.get("verbose", False)
        self.debug = self._conf.get("debug", False)

    def get(self, key):
        return self._conf.get(key, None)

    def get_distributions(self):
        if not self._dists:
            for package_set in ("host", "vm"):
                for dist in self._conf.get(package_set, []):
                    self._dists.append(Dist(f"{package_set}-{dist}"))
        return self._dists

    def get_stages(self):
        if not self._stages:
            for stage_name in STAGES:
                self._stages[stage_name] = self.parse_stage_from_config(stage_name)
        return self._stages

    def get_components(self):
        if not self._components:
            for c in self._conf.get("components", []):
                self._components.append(self.parse_component_from_config(c))
        return self._components

    def get_artifacts_dir(self):
        return self._artifacts_dir

    @staticmethod
    def get_plugins_dir():
        return PROJECT_PATH / "qubesbuilder" / "plugins"

    def parse_stage_from_config(self, stage_name: str):
        executor = None
        default_executor = self._conf.get("executor", {})
        executor_type = default_executor.get("type", "docker")
        executor_options = default_executor.get("options", {"image": "qubes-builder-fedora:latest"})

        for s in self._conf.get("stages", []):
            if isinstance(s, str):
                continue
            if stage_name != next(iter(s.keys())):
                continue
            stage_options = next(iter(s.values()))
            if stage_options.get("executor", None) and \
                    stage_options["executor"].get("type", None):
                executor_type = stage_options["executor"]["type"]
                executor_options = stage_options["executor"].get("options", {})
                executor = getExecutor(executor_type, executor_options)
                break
        if not executor:
            # FIXME: default executor?
            executor = getExecutor(executor_type, executor_options)
        stage = {"executor": executor}
        return stage

    def parse_component_from_config(self, component_name: Union[str, Dict]) -> Component:
        component_default_url = f"https://github.com/QubesOS/qubes-{component_name}"
        component_default_branch = "master"
        if isinstance(component_name, str):
            component_name = {component_name: {}}
        component_name, component_options = next(iter(component_name.items()))
        insecure_skip_checking = \
            component_name in self._conf.get("insecure-skip-checking", [])
        less_secure_signed_commits_sufficient = \
            component_name in self._conf.get("less-secure-signed-commits-sufficient", [])
        component = Component(
            source_dir=self._artifacts_dir / "sources" / component_name,
            url=component_options.get("url", component_default_url),
            branch=component_options.get("branch", component_default_branch),
            maintainers=component_options.get("maintainers", []),
            insecure_skip_checking=insecure_skip_checking,
            less_secure_signed_commits_sufficient=less_secure_signed_commits_sufficient
        )
        return component
