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
from typing import Union, List, Dict, Any, IO

import yaml
import os

from qubesbuilder.common import PROJECT_PATH
from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.template import QubesTemplate
from qubesbuilder.exc import ConfigError
from qubesbuilder.executors.helpers import getExecutor
from qubesbuilder.log import get_logger


STAGES = ["fetch", "prep", "build", "post", "verify", "sign", "publish"]
STAGES_ALIAS = {
    "f": "fetch",
    "pr": "prep",
    "b": "build",
    "po": "post",
    "v": "verify",
    "s": "sign",
    "pu": "publish",
}
log = get_logger("config")


class Config:
    def __init__(self, conf_file: Union[Path, str]):
        # Parse builder configuration file
        self._conf = self.parse_configuration_file(conf_file)

        # Qubes OS distributions
        self._dists: List = []

        # Default Qubes OS build pipeline stages
        self._stages: dict = {}

        # Qubes OS components
        self._components: List[QubesComponent] = []

        # Qubes OS Templates
        self._templates: List[QubesComponent] = []

        # Artifacts directory location
        if self._conf.get("artifacts-dir", None):
            self._artifacts_dir = Path(self._conf["artifacts-dir"]).resolve()
            log.info(f"Using '{self._artifacts_dir}' as artifacts directory.")
        else:
            self._artifacts_dir = PROJECT_PATH / "artifacts"
            log.info(f"Using '{self._artifacts_dir}' as artifacts directory.")

        self.verbose = self._conf.get("verbose", False)
        self.debug = self._conf.get("debug", False)

    @staticmethod
    def parse_configuration_file(conf_file: Union[Path, str]):
        if isinstance(conf_file, str):
            conf_file = Path(conf_file).resolve()

        if not conf_file.exists():
            raise ConfigError(f"Cannot find config '{conf_file}'.")

        try:
            with open(conf_file) as f:
                conf = yaml.safe_load(f.read())
                included_conf = conf.get("include", [])
                conf.pop("include", None)
                final_conf: Dict[str, Union[str, Any]] = {}
            for inc in included_conf:
                inc_path = Path(inc)
                if not inc_path.exists():
                    raise ConfigError(
                        f"Cannot find included builder configuration '{inc_path}'."
                    )
                try:
                    data = yaml.safe_load(inc_path.read_text())
                    final_conf.update(data)
                except yaml.YAMLError as e:
                    raise ConfigError(
                        f"Failed to parse included config '{inc_path}'."
                    ) from e
            final_conf.update(conf)

            for key in ("distributions", "templates", "components", "stages", "plugins"):
                if f"+{key}" in final_conf.keys():
                    final_conf.setdefault(key, [])
                    final_conf[key] += final_conf[f"+{key}"]
            return final_conf
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse config '{conf_file}'.") from e

    def get(self, key, default=None):
        return self._conf.get(key, default)

    def set(self, key, value):
        self._conf[key] = value

    def get_distributions(self, filtered_distributions=None):
        if not self._dists:
            if filtered_distributions:
                distributions = filtered_distributions
            else:
                distributions = self._conf.get("distributions", [])
            self._dists = [QubesDistribution(dist) for dist in distributions]
        return self._dists

    def get_templates(self):
        if not self._templates:
            self._templates = [
                QubesTemplate(template) for template in self._conf.get("templates", [])
            ]
        return self._templates

    def get_stages(self):
        if not self._stages:
            for stage_name in STAGES:
                self._stages[stage_name] = self.parse_stage_from_config(stage_name)
        return self._stages

    def get_components(self, filtered_components=None):
        if not self._components:
            # Load available component information from config
            components_from_config = []
            for c in self._conf.get("components", []):
                components_from_config.append(
                    self.parse_component_from_dict_or_string(c)
                )

            # Find if components requested would have been found from config file with
            # non default values for url, maintainer, etc.
            if filtered_components:
                for fc in filtered_components:
                    filtered_component = None
                    for c in components_from_config:
                        if c.name == fc:
                            filtered_component = c
                            break
                    if not filtered_component:
                        filtered_component = self.parse_component_from_dict_or_string(
                            fc
                        )
                    self._components.append(filtered_component)
            else:
                self._components = components_from_config

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
        executor_options = default_executor.get(
            "options", {"image": "qubes-builder-fedora:latest"}
        )

        for s in self._conf.get("stages", []):
            if isinstance(s, str):
                continue
            if stage_name != next(iter(s.keys())):
                continue
            stage_options = next(iter(s.values()))
            if stage_options.get("executor", None) and stage_options["executor"].get(
                "type", None
            ):
                executor_type = stage_options["executor"]["type"]
                executor_options = stage_options["executor"].get("options", {})
                executor = getExecutor(executor_type, executor_options)
                break
        if not executor:
            # FIXME: Review and enhance default executor definition
            executor = getExecutor(executor_type, executor_options)
        stage = {"executor": executor}
        return stage

    def parse_component_from_dict_or_string(
        self, component_name: Union[str, Dict]
    ) -> QubesComponent:
        baseurl = self.get("git", {}).get("baseurl", "https://github.com")
        prefix = self.get("git", {}).get("prefix", "QubesOS/qubes-")
        branch = self.get("git", {}).get("branch", "master")
        maintainers = self.get("git", {}).get("maintainers", [])
        url = f"{baseurl}/{prefix}{component_name}"
        timeout = self.get("timeout", 3600)
        if isinstance(component_name, str):
            component_name = {component_name: {}}
        name, options = next(iter(component_name.items()))
        insecure_skip_checking = name in self._conf.get("insecure-skip-checking", [])
        less_secure_signed_commits_sufficient = name in self._conf.get(
            "less-secure-signed-commits-sufficient", []
        )
        component = QubesComponent(
            source_dir=self._artifacts_dir / "sources" / name,
            url=options.get("url", url),
            branch=options.get("branch", branch),
            maintainers=options.get("maintainers", maintainers),
            insecure_skip_checking=insecure_skip_checking,
            less_secure_signed_commits_sufficient=less_secure_signed_commits_sufficient,
            timeout=options.get("timeout", timeout)
        )
        return component
