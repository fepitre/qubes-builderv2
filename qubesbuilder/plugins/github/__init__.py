# The Qubes OS Project, http://www.qubes-os.org
#
# Copyright (C) 2022 Frédéric Pierret (fepitre) <frederic@invisiblethingslab.com>
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
from pathlib import Path

from qubesbuilder.common import PROJECT_PATH
from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import Plugin, PluginError, DistributionPlugin, TemplatePlugin
from qubesbuilder.plugins.template import TEMPLATE_VERSION
from qubesbuilder.template import QubesTemplate

log = get_logger("github")


github_issues_repo = "QubesOS/qubes-issues"
github_api_prefix = "https://api.github.com"
github_repo_prefix = "QubesOS/qubes-"
github_baseurl = "https://github.com"

fixes_re = re.compile(
    r"(fixes|closes)( (https://github.com/[^ ]+/|" r"QubesOS/Qubes-issues#)[0-9]+)",
    re.IGNORECASE,
)
issue_re = re.compile(r"QubesOS/Qubes-issues(#|/issues/)[0-9]+", re.IGNORECASE)
cleanup_re = re.compile(r"[^ ]+[#/]")
release_name_re = re.compile("r[0-9.]+")
number_re = re.compile('"number": *([0-9]+)')


class GithubError(PluginError):
    pass


class GithubPlugin(Plugin):
    """
    GithubPlugin manages release workflow from GitHub
    """

    def __init__(
        self,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        state_dir: Path,
        api_key: str,
        build_report_repo: str,
        build_issues_repo: str,
        logs_repo: str,
        qubes_release: str,
        repository_publish: dict,
        backend_vmm: str,
        log_file: Path = None,
        verbose: bool = False,
        debug: bool = False,
        component: QubesComponent = None,
        dist: QubesDistribution = None,
        template: QubesTemplate = None,
    ):
        super().__init__(
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )
        self.executor = executor
        self.state_dir = state_dir
        self.api_key = api_key
        self.build_report_repo = build_report_repo
        self.build_issues_repo = build_issues_repo
        self.logs_repo = logs_repo
        self.qubes_release = qubes_release
        self.repository_publish = repository_publish
        self.log_file = log_file
        self.backend_vmm = backend_vmm

        self.environment.update(
            {
                "PYTHONPATH": str(PROJECT_PATH),
                "HOME": os.environ["HOME"],
                "GITHUB_API_KEY": self.api_key,
                "GITHUB_BUILD_REPORT_REPO": self.build_report_repo,
            }
        )

        if component:
            self.dist = dist
            self.component = component
            self.template = None
            self.environment.update(
                {
                    "COMPONENT": self.component.name,
                    f"GIT_URL_{self.component.name.replace('-', '_')}": self.component.url,
                }
            )
        elif template:
            self.dist = template.distribution
            self.template = template
            self.component = None  # type: ignore
            self.environment.update(
                {
                    "COMPONENT": "template",
                }
            )
        else:
            raise GithubError("Please provide either component or template (not both).")

        self.src_dir = (
            str(self.component.source_dir)
            if self.component
            else f"{self.plugins_dir}/template"
        )
        self.package_name = None

    def get_package_name(self):
        if not self.package_name:
            if self.component:
                self.package_name = self.component.name  # type: ignore
            else:
                template_plugin = TemplatePlugin(
                    template=self.template,  # type: ignore
                    artifacts_dir=self.artifacts_dir,
                    plugins_dir=self.plugins_dir,
                    debug=self.debug,
                    verbose=self.verbose,
                )
                template_timestamp = template_plugin.get_template_timestamp()
                self.package_name = f"qubes-template-{self.template.name}-{TEMPLATE_VERSION}-{template_timestamp}"  # type: ignore
        return self.package_name

    def run(
        self,
        stage: str,
        repository_publish: str = None,
        **kwargs,
    ):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        # # auto-build is exporting all build logs URL into env
        # if os.environ.get("BUILD_LOGS_URL"):
        #     build_logs_url = os.environ["BUILD_LOGS_URL"].rstrip("\n").split()
        # else:
        #     raise GithubError("Please provide build logs URL.")
        #
        # for log_url in build_logs_url:
        #     if log_url.startswith(f"{self.component.name}-{self.dist.distribution}"):
        #         _, build_log_url = log_url.split("=")
        #         break
        #
        # if not build_log_url:
        #     raise GithubError(
        #         f"Cannot find build log URL for {self.dist} in BUILD_LOGS_URL environment variable."
        #     )

        if stage == "pre":
            notify_issues_cmd = [
                f"{self.plugins_dir}/github/scripts/notify-issues",
                f"--message-templates-dir={self.plugins_dir}/github/templates",
                "build",
                self.qubes_release,
                self.src_dir,
                self.get_package_name(),
                self.dist.distribution,  # type: ignore
                "building",
            ]
            cmd = [" ".join(notify_issues_cmd)]
            try:
                self.executor.run(cmd, environment=self.environment)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to notify GitHub."
                raise GithubError(msg) from e

        if stage == "post":
            build_success = False
            # Report build failure if no build artifacts is found
            if self.component:
                distribution_plugin = DistributionPlugin(
                    component=self.component,
                    artifacts_dir=self.artifacts_dir,
                    dist=self.dist,  # type: ignore
                    plugins_dir=self.plugins_dir,
                    backend_vmm=self.backend_vmm,
                    debug=self.debug,
                    verbose=self.verbose,
                )
                build_success = all(
                    distribution_plugin.get_dist_artifacts_info(
                        stage="build", basename=build.with_suffix("")
                    )
                    for build in distribution_plugin.parameters["build"]
                )
            elif self.template:
                template_plugin = TemplatePlugin(
                    template=self.template,
                    artifacts_dir=self.artifacts_dir,
                    plugins_dir=self.plugins_dir,
                    debug=self.debug,
                    verbose=self.verbose,
                )
                if template_plugin.get_artifacts_info(stage="build"):
                    build_success = True

            if not build_success:
                notify_issues_cmd = [
                    f"{self.plugins_dir}/github/scripts/notify-issues",
                    f"--message-templates-dir={self.plugins_dir}/github/templates",
                    f"--build-log={self.log_file if self.log_file else None}",
                    "build",
                    self.qubes_release,
                    self.src_dir,
                    self.get_package_name(),
                    self.dist.distribution,  # type: ignore
                    "failed",
                ]
                cmd = [" ".join(notify_issues_cmd)]
                try:
                    self.executor.run(cmd, environment=self.environment)
                except ExecutorError as e:
                    msg = f"{self.component}:{self.dist}: Failed to notify GitHub."
                    raise GithubError(msg) from e

        if stage == "upload":
            repository_publish = repository_publish or self.repository_publish.get(
                "components" if self.component else "templates", None
            )
            if not repository_publish:
                raise GithubError("Please provide publish repository.")

            state_file = (
                self.state_dir
                / f"{self.qubes_release}-{self.component.name if self.component else 'template'}-{self.dist.package_set}-{self.dist.name}-{repository_publish}"  # type: ignore
            )
            stable_state_file = (
                self.state_dir
                / f"{self.qubes_release}-{self.component.name if self.component else 'template'}-{self.dist.package_set}-{self.dist.name}-current"  # type: ignore
            )
            notify_issues_cmd = [
                f"{self.plugins_dir}/github/scripts/notify-issues",
                f"--message-templates-dir={self.plugins_dir}/github/templates",
                f"--build-log={self.log_file if self.log_file else None}",
                "upload",
                self.qubes_release,
                self.src_dir,
                self.get_package_name(),
                self.dist.distribution,  # type: ignore
                str(repository_publish),
                str(state_file),
                str(stable_state_file),
            ]
            cmd = [" ".join(notify_issues_cmd)]
            try:
                self.executor.run(cmd, environment=self.environment)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to notify GitHub."
                raise GithubError(msg) from e
