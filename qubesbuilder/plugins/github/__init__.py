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
from pathlib import Path

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import DistributionPlugin, PluginError

log = get_logger("github")


class GithubError(PluginError):
    pass


class GithubPlugin(DistributionPlugin):
    """
    GithubPlugin manages release workflow from GitHub
    """

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        backend_vmm: str,
        state_dir: Path,
        api_key: str,
        build_report_repo: str,
        build_issues_repo: str,
        logs_repo: str,
        qubes_release: str,
        repository_publish: dict,
        verbose: bool = False,
        debug: bool = False,
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
        self.executor = executor
        self.state_dir = state_dir
        self.api_key = api_key
        self.build_report_repo = build_report_repo
        self.build_issues_repo = build_issues_repo
        self.logs_repo = logs_repo
        self.qubes_release = qubes_release
        self.repository_publish = repository_publish

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

        if stage == "publish":
            repository_publish = repository_publish or self.repository_publish.get(
                "components", "current-testing"
            )

            # auto-build is exporting all build logs URL into env
            if os.environ.get("BUILD_LOGS_URL"):
                build_logs_url = os.environ["BUILD_LOGS_URL"].rstrip("\n").split()
            else:
                raise GithubError("Please provide build logs URL.")

            build_log_url = None
            for log_url in build_logs_url:
                if log_url.startswith(
                    f"{self.component.name}-{self.dist.distribution}"
                ):
                    _, build_log_url = log_url.split("=")
                    break

            if not build_log_url:
                raise GithubError(
                    f"Cannot find build log URL for {self.dist} in BUILD_LOGS_URL environment variable."
                )

            state_file = (
                self.state_dir
                / f"{self.qubes_release}-{self.component.name}-{self.dist.package_set}-{self.dist.name}-{repository_publish}"
            )
            stable_state_file = (
                self.state_dir
                / f"{self.qubes_release}-{self.component.name}-{self.dist.package_set}-{self.dist.name}-current"
            )
            notify_issues_cmd = [
                f"{self.plugins_dir}/github/scripts/notify-issues",
                f"--build-log={build_log_url}",
                "upload",
                f"{self.qubes_release}",
                f"{self.component.source_dir}",
                f"{self.component.name}",
                self.dist.name,
                self.dist.package_set,
                repository_publish,
                str(state_file),
                str(stable_state_file),
            ]
            cmd = [" ".join(notify_issues_cmd)]
            self.environment.update(
                {
                    "HOME": os.environ["HOME"],
                    "COMPONENT": self.component.name,
                    "GITHUB_API_KEY": self.api_key,
                    "GITHUB_BUILD_REPORT_REPO": self.build_report_repo,
                    f"GIT_URL_{self.component.name.replace('-', '_')}": self.component.url,
                }
            )
            try:
                self.executor.run(cmd, environment=self.environment)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to notify GitHub."
                raise GithubError(msg) from e
