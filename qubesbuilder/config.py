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

from copy import deepcopy
from pathlib import Path
from typing import Union, List, Dict, Any

import yaml

from qubesbuilder.common import PROJECT_PATH, VerificationMode
from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.exc import ConfigError
from qubesbuilder.executors import ExecutorError
from qubesbuilder.executors.container import ContainerExecutor
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.executors.qubes import QubesExecutor
from qubesbuilder.log import get_logger
from qubesbuilder.template import QubesTemplate

log = get_logger("config")


def deep_merge(a: dict, b: dict, allow_append: bool = False) -> dict:
    result = deepcopy(a)
    for b_key, b_value in b.items():
        a_value = result.get(b_key, None)
        if isinstance(a_value, dict) and isinstance(b_value, dict):
            result[b_key] = deep_merge(a_value, b_value, allow_append)
        else:
            if allow_append and isinstance(result.get(b_key, None), list):
                result[b_key] += deepcopy(b_value)
            else:
                result[b_key] = deepcopy(b_value)
    return result


class Config:
    def __init__(self, conf_file: Union[Path, str], options: dict = None):
        # Keep path of configuration file
        self._conf_file = conf_file

        # Parse builder configuration file
        self._conf = self.parse_configuration_file(conf_file, options)

        # Qubes OS distributions
        self._dists: List = []

        # Default Qubes OS build pipeline stages
        self._stages: Dict = {}

        # Qubes OS components
        self._components: List[QubesComponent] = []

        # Qubes OS Templates
        self._templates: List[QubesTemplate] = []

        # Artifacts directory location
        self._artifacts_dir: Path = None  # type: ignore

        # Plugins directories
        self._plugins_dirs: List[Path] = [PROJECT_PATH / "qubesbuilder" / "plugins"]

    # fmt: off
    # Mypy does not support this form yet (see https://github.com/python/mypy/issues/8083).
    verbose: Union[bool, property]                       = property(lambda self: self.get("verbose", False))
    debug: Union[bool, property]                         = property(lambda self: self.get("debug", False))
    force_fetch: Union[bool, property]                   = property(lambda self: self.get("force-fetch", False))
    skip_git_fetch: Union[bool, property]                = property(lambda self: self.get("skip-git-fetch", False))
    fetch_versions_only: Union[bool, property]           = property(lambda self: self.get("fetch-versions-only", False))
    backend_vmm: Union[str, property]                    = property(lambda self: self.get("backend-vmm", ""))
    use_qubes_repo: Union[Dict, property]                = property(lambda self: self.get("use-qubes-repo", {}))
    gpg_client: Union[str, property]                     = property(lambda self: self.get("gpg-client", "gpg"))
    sign_key: Union[Dict, property]                      = property(lambda self: self.get("sign-key", {}))
    min_age_days: Union[int, property]                   = property(lambda self: self.get("min-age-days", 5))
    qubes_release: Union[str, property]                  = property(lambda self: self.get("qubes-release", ""))
    repository_publish: Union[Dict, property]            = property(lambda self: self.get("repository-publish", {}))
    repository_upload_remote_host: Union[Dict, property] = property(lambda self: self.get("repository-upload-remote-host", {}))
    template_root_size: Union[str, property]             = property(lambda self: self.get("template-root-size", "20G"))
    template_root_with_partitions: Union[bool, property] = property(lambda self: self.get("template-root-with-partitions", True))
    installer_kickstart: Union[str, property]            = property(lambda self: self.get("iso", {}).get("kickstart", "conf/qubes-kickstart.cfg"))
    iso_version: Union[str, property]                    = property(lambda self: self.get("iso", {}).get("version", ""))
    iso_flavor: Union[str, property]                     = property(lambda self: self.get("iso", {}).get("flavor", ""))
    iso_use_kernel_latest: Union[bool, property]         = property(lambda self: self.get("iso", {}).get("use-kernel-latest", False))
    increment_devel_versions: Union[bool, property]       = property(lambda self: self.get("increment-devel-versions", False))
    # fmt: on

    def __repr__(self):
        return f"<Config {str(self._conf_file)}>"

    @classmethod
    def _load_config(cls, conf_file: Path, options: dict = None):
        if not conf_file.exists():
            raise ConfigError(f"Cannot find builder configuration '{conf_file}'.")
        try:
            conf = yaml.safe_load(conf_file.read_text())
        except yaml.YAMLError as e:
            raise ConfigError(f"Failed to parse config '{conf_file}'.") from e

        included_conf = conf.get("include", [])
        conf.pop("include", None)

        included_data = []
        for inc in included_conf:
            inc_path = Path(inc)
            if not inc_path.is_absolute():
                inc_path = conf_file.parent / inc_path
            included_data.append(cls._load_config(inc_path))
        if options and isinstance(options, dict):
            included_data.append(options)

        # Init the final config based on included configs first
        combined_conf: Dict[str, Any] = {}
        for data in included_data:
            for key in data:
                if key in (
                    "+distributions",
                    "+templates",
                    "+components",
                    "+stages",
                    "+plugins",
                ):
                    combined_conf.setdefault(key, [])
                    combined_conf[key] += data[key]
                else:
                    # if conf top-level key is not defined or is a list we override by
                    # the included values, else we merge the two dicts where included
                    # values may override original ones.
                    if not combined_conf.get(key, None) or isinstance(
                        combined_conf[key], list
                    ):
                        combined_conf[key] = data[key]
                    elif isinstance(combined_conf[key], dict):
                        combined_conf[key] = deep_merge(combined_conf[key], data[key])

        # Override included values from main config
        for key in conf:
            if key in (
                "+distributions",
                "+templates",
                "+components",
                "+stages",
                "+plugins",
            ):
                combined_conf.setdefault(key, [])
                combined_conf[key] += conf[key]
            else:
                combined_conf[key] = conf[key]

        # Allow options to override only values that can be merged
        if options and isinstance(options, dict):
            for key in options:
                if not key.startswith("+") and key not in (
                    "distributions",
                    "templates",
                    "components",
                    "stages",
                    "plugins",
                ):
                    if isinstance(combined_conf[key], dict) and isinstance(
                        options[key], dict
                    ):
                        combined_conf[key] = deep_merge(
                            combined_conf[key], options[key]
                        )
                    else:
                        combined_conf[key] = options[key]

        return combined_conf

    @classmethod
    def parse_configuration_file(
        cls, conf_file: Union[Path, str], options: Dict = None
    ):
        if isinstance(conf_file, str):
            conf_file = Path(conf_file).resolve()

        final_conf = cls._load_config(conf_file, options)

        # Merge dict from included configs
        for key in (
            "distributions",
            "templates",
            "components",
            "stages",
            "plugins",
        ):
            if f"+{key}" in final_conf.keys():
                merged_result: Dict[str, Dict] = {}
                final_conf.setdefault(key, [])
                final_conf.setdefault(f"+{key}", [])
                # Iterate over all key and +key in order to merge dicts
                for s in final_conf[key] + final_conf[f"+{key}"]:
                    if isinstance(s, str) and not merged_result.get(s, None):
                        merged_result[s] = {}
                    if isinstance(s, dict):
                        if not merged_result.get(next(iter(s.keys())), None):
                            merged_result[next(iter(s.keys()))] = next(iter(s.values()))
                        else:
                            merged_result[next(iter(s.keys()))] = deep_merge(
                                merged_result[next(iter(s.keys()))],
                                next(iter(s.values())),
                            )
                # Set final value based on merged dict
                final_conf[key] = []
                for k, v in merged_result.items():
                    if not v:
                        final_conf[key].append(k)
                    else:
                        final_conf[key].append({k: v})
        return final_conf

    def get(self, key, default=None):
        return self._conf.get(key, default)

    def set(self, key, value):
        self._conf[key] = value

    def get_distributions(self, filtered_distributions=None):
        if not self._dists:
            distributions = self._conf.get("distributions", [])
            self._dists = [QubesDistribution(dist) for dist in distributions]
        if filtered_distributions:
            result = []
            for fd in filtered_distributions:
                for d in self._dists:
                    if d.distribution == fd:
                        result.append(d)
                        break
                else:
                    raise ConfigError(f"No such distribution: {fd}")
            return result
        return self._dists

    def get_templates(self, filtered_templates=None):
        if not self._templates:
            templates = self._conf.get("templates", [])
            self._templates = [QubesTemplate(template) for template in templates]
        if filtered_templates:
            result = []
            for ft in filtered_templates:
                for t in self._templates:
                    if t.name == ft:
                        result.append(t)
                        break
                else:
                    raise ConfigError(f"No such template: {ft}")
            return result
        return self._templates

    def get_components(self, filtered_components=None, url_match=False):
        if not self._components:
            # Load available component information from config
            components_from_config = []
            for c in self._conf.get("components", []):
                components_from_config.append(self.get_component_from_dict_or_string(c))

            self._components = components_from_config

        # Find if components requested would have been found from config file with
        # non default values for url, maintainer, etc.
        if filtered_components:
            result = []
            prefix = self.get("git", {}).get("prefix", "QubesOS/qubes-")
            for fc in filtered_components:
                found = False
                for c in self._components:
                    if c.name == fc:
                        result.append(c)
                        found = True
                    elif url_match and c.url.partition(prefix)[2] == fc:
                        result.append(c)
                        found = True
                if not found:
                    raise ConfigError(f"No such component: {fc}")
            return result
        else:
            return self._components

    @property
    def artifacts_dir(self):
        if not self._artifacts_dir:
            if self._conf.get("artifacts-dir", None):
                self._artifacts_dir = Path(self._conf["artifacts-dir"]).resolve()
            else:
                self._artifacts_dir = PROJECT_PATH / "artifacts"
        return self._artifacts_dir

    def get_logs_dir(self):
        return self.artifacts_dir / "logs"

    def get_plugins_dirs(self):
        plugins_dirs = self._conf.get("plugins-dirs", [])
        # We call get_components in order to ensure that plugin ones are added
        # in _plugins_dirs.
        self.get_components()
        for d in self._plugins_dirs:
            d_path = Path(d).expanduser().resolve()
            if d not in plugins_dirs:
                plugins_dirs = plugins_dirs + [str(d_path)]
        return plugins_dirs

    def get_executor_from_config(self, stage_name: str):
        if self._stages.get(stage_name, {}).get("executor", None):
            return self._stages[stage_name]["executor"]

        self._stages.setdefault(stage_name, {}).setdefault("executor", None)
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
                self._stages[stage_name]["executor"] = self.get_executor(
                    executor_type, executor_options
                )
                break
        if not self._stages[stage_name]["executor"]:
            # FIXME: Review and enhance default executor definition
            self._stages[stage_name]["executor"] = self.get_executor(
                executor_type, executor_options
            )

        return self._stages[stage_name]["executor"]

    def get_component_from_dict_or_string(
        self, component_name: Union[str, Dict]
    ) -> QubesComponent:
        baseurl = self.get("git", {}).get("baseurl", "https://github.com")
        prefix = self.get("git", {}).get("prefix", "QubesOS/qubes-")
        suffix = self.get("git", {}).get("suffix", ".git")
        branch = self.get("git", {}).get("branch", "master")
        maintainers = self.get("git", {}).get("maintainers", [])
        timeout = self.get("timeout", 3600)

        if isinstance(component_name, str):
            component_name = {component_name: {}}

        name, options = next(iter(component_name.items()))
        source_dir = self.artifacts_dir / "sources" / name
        url = f"{baseurl}/{options.get('prefix', prefix)}{name}{options.get('suffix', suffix)}"
        verification_mode = VerificationMode.SignedTag
        if name in self._conf.get("insecure-skip-checking", []):
            verification_mode = VerificationMode.Insecure
        if name in self._conf.get("less-secure-signed-commits-sufficient", []):
            verification_mode = VerificationMode.SignedCommit
        if "verification-mode" in options:
            verification_mode = VerificationMode(options["verification-mode"])
        fetch_versions_only = options.get(
            "fetch-versions-only", self.get("fetch-versions-only", False)
        )
        is_plugin = options.get("plugin", False)

        component_kwargs = {
            "source_dir": source_dir,
            "url": options.get("url", url),
            "branch": options.get("branch", branch),
            "maintainers": options.get("maintainers", maintainers),
            "verification_mode": verification_mode,
            "timeout": options.get("timeout", timeout),
            "fetch_versions_only": fetch_versions_only,
            "is_plugin": is_plugin
        }
        if self.increment_devel_versions:
            component_kwargs["devel_path"] = (
                self.artifacts_dir / "components" / name / "noversion" / "devel"
            )
        if is_plugin:
            plugin_dir = source_dir
            if options.get("content-dir", None):
                plugin_dir = source_dir / options["content-dir"]
            self._plugins_dirs.append(plugin_dir)
        component = QubesComponent(**component_kwargs)
        return component

    @staticmethod
    def get_executor(executor_type, executor_options):
        if executor_type in ("podman", "docker"):
            executor = ContainerExecutor(executor_type, **executor_options)
        elif executor_type == "local":
            executor = LocalExecutor(**executor_options)  # type: ignore
        elif executor_type == "qubes":
            executor = QubesExecutor(**executor_options)  # type: ignore
        else:
            raise ExecutorError("Cannot determine which executor to use.")
        return executor
