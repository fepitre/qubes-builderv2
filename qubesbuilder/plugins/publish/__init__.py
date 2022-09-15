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

import datetime
from pathlib import Path

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import DistributionPlugin, PluginError

log = get_logger("publish")

# Define the minimum age for which packages can be published to 'current'
COMPONENT_REPOSITORIES = ["current", "current-testing", "security-testing", "unstable"]


class PublishError(PluginError):
    pass


class PublishPlugin(DistributionPlugin):
    """
    PublishPlugin manages generic distribution publication.

    Stages:
        - publish - Ensure all build targets artifacts exist from previous required stages.

    Entry points:
        - build
    """

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        qubes_release: str,
        gpg_client: str,
        sign_key: dict,
        repository_publish: dict,
        backend_vmm: str,
        min_age_days: int,
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(
            executor=executor,
            component=component,
            dist=dist,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
            backend_vmm=backend_vmm,
        )

        self.executor = executor
        self.qubes_release = qubes_release
        self.repository_publish = repository_publish
        self.gpg_client = gpg_client
        self.sign_key = sign_key
        self.min_age_days = min_age_days

    def validate_repository_publish(self, repository_publish):
        if repository_publish not in (
            "current",
            "current-testing",
            "security-testing",
            "unstable",
        ):
            msg = (
                f"{self.component}:{self.dist}: "
                f"Refusing to publish components into '{repository_publish}'."
            )
            raise PublishError(msg)

    def is_published(self, basename, repository):
        publish_info = self.get_dist_artifacts_info(stage="publish", basename=basename)
        if not publish_info:
            return False
        return repository in [
            r["name"] for r in publish_info.get("repository-publish", [])
        ]

    def can_be_published_in_stable(self, basename, ignore_min_age):
        # Check packages are published
        if not self.is_published(basename, "current-testing"):
            return False

        # Check minimum day that packages are available for testing
        publish_info = self.get_dist_artifacts_info(stage="publish", basename=basename)
        publish_date = None
        for r in publish_info["repository-publish"]:
            if r["name"] == "current-testing":
                publish_date = datetime.datetime.strptime(r["timestamp"], "%Y%m%d%H%M")
                break

        if not publish_date:
            log.error("Something wrong detected in repositories. Missing timestamp?")
            return False

        # Check that packages have been published before threshold_date
        threshold_date = datetime.datetime.utcnow() - datetime.timedelta(
            days=self.min_age_days
        )
        if not ignore_min_age and publish_date > threshold_date:
            return False

        return True

    def run(self, stage: str):
        if stage == "publish":
            if not isinstance(self.executor, LocalExecutor):
                raise PublishError("This plugin only supports local executor.")

            # Check if we have Debian related content defined
            if not self.parameters.get("build", []):
                log.info(f"{self.component}:{self.dist}: Nothing to be done.")
                return
