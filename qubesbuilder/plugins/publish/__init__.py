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
import os
from pathlib import Path

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor
from qubesbuilder.executors.local import LocalExecutor
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import DistributionPlugin, PluginError

log = get_logger("publish")

# Define the minimum age for which packages can be published to 'current'
MIN_AGE_DAYS = 5


class PublishError(PluginError):
    pass


class PublishPlugin(DistributionPlugin):
    """
    PublishPlugin manages generic distribution publication.
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
        )

        self.executor = executor
        self.verbose = verbose
        self.debug = debug
        self.qubes_release = qubes_release
        self.repository_publish = repository_publish
        self.gpg_client = gpg_client
        self.sign_key = sign_key

    def run(self, stage: str):
        if stage == "publish" and not isinstance(self.executor, LocalExecutor):
            raise PublishError("This plugin only supports local executor.")

    def is_published_in_stable(self, basename, ignore_min_age):
        failure_msg = (
            f"{self.component}:{self.dist}:{basename}: "
            f"Refusing to publish to 'current' as packages are not "
            f"uploaded to 'current-testing' or 'security-testing' "
            f"for at least {MIN_AGE_DAYS} days."
        )
        # Check packages are published
        publish_info = self.get_artifacts_info(stage="publish", basename=basename)
        if not publish_info:
            raise PublishError(failure_msg)

        # Check for valid repositories under which packages are published
        if publish_info.get("repository-publish", None) not in (
            "security-testing",
            "current-testing",
            "current",
        ):
            raise PublishError(failure_msg)
        # If publish repository is 'current' we check the next spec file
        if publish_info["repository-publish"] == "current":
            log.info(
                f"{self.component}:{self.dist}:{basename}: "
                f"Already published to 'current'."
            )
            return True

        # Check minimum day that packages are available for testing
        publish_date = datetime.datetime.utcfromtimestamp(
            os.stat(
                self.get_dist_component_artifacts_dir("publish")
                / f"{basename}.publish.yml"
            ).st_mtime
        )
        # Check that packages have been published before threshold_date
        threshold_date = datetime.datetime.utcnow() - datetime.timedelta(
            days=MIN_AGE_DAYS
        )
        if not ignore_min_age and publish_date > threshold_date:
            raise PublishError(failure_msg)
        return False
