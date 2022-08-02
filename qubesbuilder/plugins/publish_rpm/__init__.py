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
import os
import shutil
from datetime import datetime
from pathlib import Path

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins.publish import PublishPlugin, PublishError, MIN_AGE_DAYS

log = get_logger("publish_rpm")


class RPMPublishPlugin(PublishPlugin):
    """
    RPMPublishPlugin manages RPM distribution publication.
    """

    plugin_dependencies = ["publish", "sign_rpm"]

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
        verbose: bool = False,
        debug: bool = False,
    ):
        super().__init__(
            component=component,
            dist=dist,
            plugins_dir=plugins_dir,
            executor=executor,
            artifacts_dir=artifacts_dir,
            qubes_release=qubes_release,
            gpg_client=gpg_client,
            sign_key=sign_key,
            repository_publish=repository_publish,
            verbose=verbose,
            debug=debug,
            backend_vmm=backend_vmm,
        )

    def createrepo(self, build, target_dir):
        log.info(f"{self.component}:{self.dist}:{build}: Updating metadata.")
        cmd = [f"cd {target_dir}", "createrepo_c -g comps.xml ."]
        try:
            shutil.rmtree(target_dir / "repodata")
            self.executor.run(cmd)
        except (ExecutorError, OSError) as e:
            msg = f"{self.component}:{self.dist}:{build}: Failed to 'createrepo_c'"
            raise PublishError(msg) from e

    def sign_metadata(self, build, sign_key, target_dir):
        log.info(f"{self.component}:{self.dist}:{build}: Signing metadata.")
        repomd = target_dir / "repodata/repomd.xml"
        cmd = [
            f"{self.gpg_client} --batch --no-tty --yes --detach-sign --armor -u {sign_key} {repomd} > {repomd}.asc",
        ]
        try:
            self.executor.run(cmd)
        except (ExecutorError, OSError) as e:
            msg = f"{self.component}:{self.dist}:{build}:  Failed to sign metadata"
            raise PublishError(msg) from e

    def publish(self, build, sign_key, db_path, repository_publish):
        # spec file basename will be used as prefix for some artifacts
        build_bn = build.mangle()

        # Read information from build stage
        build_info = self.get_dist_artifacts_info(stage="build", basename=build_bn)

        if not build_info.get("rpms", []) and not build_info.get("srpm", None):
            log.info(f"{self.component}:{self.dist}:{build}: Nothing to publish.")
            return

        # Publish packages with hardlinks to built RPMs
        log.info(
            f"{self.component}:{self.dist}:{build}: Publishing RPMs to '{repository_publish}'."
        )

        # Source artifacts
        prep_artifacts_dir = self.get_dist_component_artifacts_dir(stage="prep")
        # Build artifacts
        build_artifacts_dir = self.get_dist_component_artifacts_dir(stage="build")
        # Publish repository
        artifacts_dir = self.get_repository_publish_dir() / self.dist.type

        packages_list = [
            build_artifacts_dir / "rpm" / rpm for rpm in build_info["rpms"]
        ]
        packages_list += [prep_artifacts_dir / build_info["srpm"]]

        # We check that signature exists (--check-only option)
        log.info(f"{self.component}:{self.dist}:{build}: Verifying signatures.")
        try:
            for rpm in packages_list:
                cmd = [
                    f"{self.plugins_dir}/sign_rpm/scripts/sign-rpm "
                    f"--sign-key {sign_key} --db-path {db_path} --rpm {rpm} --check-only"
                ]
                self.executor.run(cmd)
        except ExecutorError as e:
            msg = f"{self.component}:{self.dist}:{build}: Failed to check signatures."
            raise PublishError(msg) from e

        target_dir = (
            artifacts_dir
            / f"{self.qubes_release}/{repository_publish}/{self.dist.package_set}/{self.dist.name}"
        )
        try:
            for rpm in packages_list:
                target_path = target_dir / "rpm" / rpm.name
                target_path.unlink(missing_ok=True)
                # target_path.hardlink_to(rpm)
                os.link(rpm, target_path)
        except (ValueError, PermissionError, NotImplementedError) as e:
            msg = f"{self.component}:{self.dist}:{build}: Failed to publish packages."
            raise PublishError(msg) from e

        # Createrepo published RPMs
        self.createrepo(build=build, target_dir=target_dir)

        # Sign metadata
        self.sign_metadata(build=build, sign_key=sign_key, target_dir=target_dir)

    def unpublish(self, build, sign_key, repository_publish):
        # spec file basename will be used as prefix for some artifacts
        build_bn = build.mangle()
        # Read information from build stage
        build_info = self.get_dist_artifacts_info(stage="build", basename=build_bn)

        if not build_info.get("rpms", []) and not build_info.get("srpm", None):
            log.info(f"{self.component}:{self.dist}:{build}: Nothing to unpublish.")
            return

        log.info(
            f"{self.component}:{self.dist}:{build}: Unpublishing RPMs from '{repository_publish}'."
        )

        # Source artifacts
        prep_artifacts_dir = self.get_dist_component_artifacts_dir(stage="prep")
        # Build artifacts
        build_artifacts_dir = self.get_dist_component_artifacts_dir(stage="build")

        packages_list = [
            build_artifacts_dir / "rpm" / rpm for rpm in build_info["rpms"]
        ]
        packages_list += [prep_artifacts_dir / build_info["srpm"]]

        # If exists, remove hardlinks to built RPMs
        artifacts_dir = self.get_repository_publish_dir() / self.dist.type
        target_dir = (
            artifacts_dir
            / f"{self.qubes_release}/{repository_publish}/{self.dist.package_set}/{self.dist.name}"
        )
        try:
            for rpm in packages_list:
                target_path = target_dir / "rpm" / rpm.name
                target_path.unlink(missing_ok=True)
        except (ValueError, PermissionError, NotImplementedError) as e:
            msg = f"{self.component}:{self.dist}:{build}: Failed to unpublish packages."
            raise PublishError(msg) from e

        # Createrepo unpublished RPMs
        self.createrepo(build=build, target_dir=target_dir)

        # Sign metadata
        self.sign_metadata(build=build, sign_key=sign_key, target_dir=target_dir)

    def create_metalink(self, repository_publish):
        repository_dir = (
            self.get_repository_publish_dir()
            / self.dist.type
            / self.qubes_release
            / repository_publish
            / self.dist.package_set
            / self.dist.name
        )
        repomd = repository_dir / "repodata/repomd.xml"
        if not repomd.exists():
            msg = f"{self.component}:{self.dist}: Cannot find repomd '{repomd}'."
            raise PublishError(msg)

        log.info(f"Creating metalink for {repomd}.")
        try:
            cmd = [
                f"mkmetalink -b {repository_dir} -- {self.plugins_dir}/publish_rpm/mirrors.list {repomd} > {repomd}.metalink"
            ]
            self.executor.run(cmd)
        except ExecutorError as e:
            msg = f"{self.component}:{self.dist}: Failed to create metalink for '{repomd}'."
            log.error(msg)

    def run(
        self,
        stage: str,
        repository_publish: str = None,
        ignore_min_age: bool = False,
        unpublish: bool = False,
        **kwargs,
    ):
        """
        Run plugin for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        # Check if we have a signing key provided
        sign_key = self.sign_key.get(self.dist.distribution, None) or self.sign_key.get(
            "rpm", None
        )
        if not sign_key:
            log.info(f"{self.component}:{self.dist}: No signing key found.")
            return

        # Check if we have a gpg client provided
        if not self.gpg_client:
            log.info(f"{self.component}: Please specify GPG client to use!")
            return

        # FIXME: Refactor the code handling both standard and template components.
        #  It applies for other plugins.

        if stage == "publish":
            repository_publish = repository_publish or self.repository_publish.get(
                "components"
            )
            if not repository_publish:
                raise PublishError("Cannot determine repository for publish")

        # Publish stage for standard (not template) components
        if stage == "publish" and not unpublish:
            # Sign artifacts
            sign_artifacts_dir = self.get_dist_component_artifacts_dir(stage="sign")

            # repository-publish directory
            artifacts_dir = self.get_repository_publish_dir() / self.dist.type

            # marmarek: see comment in sign_rpm, probably should be some per-key directory, not copied for every component
            # Ensure dbpath from sign stage (still) exists
            db_path = sign_artifacts_dir / "rpmdb"
            if not db_path.exists():
                msg = f"{self.component}: {self.dist}: Failed to find RPM DB path."
                raise PublishError(msg)

            # marmarek: should this be done only if not exists yet?
            # Create publish repository skeleton
            comps = (
                self.plugins_dir
                / f"publish_rpm/comps/comps-{self.dist.package_set}.xml"
            )
            create_skeleton_cmd = [
                f"{self.plugins_dir}/publish_rpm/scripts/create-skeleton",
                self.qubes_release,
                self.dist.package_set,
                self.dist.name,
                str(artifacts_dir.absolute()),
                str(comps.absolute()),
            ]
            cmd = [" ".join(create_skeleton_cmd)]
            try:
                self.executor.run(cmd)
            except ExecutorError as e:
                msg = f"{self.component}:{self.dist}: Failed to create repository skeleton."
                raise PublishError(msg) from e

            # Check if publish repository is valid
            self.validate_repository_publish(repository_publish)

            # Check if we already published packages into the provided repository
            if all(
                self.is_published(
                    basename=build.mangle(), repository=repository_publish
                )
                for build in self.parameters["build"]
            ):
                log.info(
                    f"{self.component}:{self.dist}: Already published to '{repository_publish}'."
                )
                # Update metalink in case of previous failure on creating it
                self.create_metalink(repository_publish)
                return

            # Check if we can publish into current
            if repository_publish == "current" and not all(
                self.can_be_published_in_stable(
                    basename=build.mangle(), ignore_min_age=ignore_min_age
                )
                for build in self.parameters["build"]
            ):
                failure_msg = (
                    f"{self.component}:{self.dist}: "
                    f"Refusing to publish to 'current' as packages are not "
                    f"uploaded to 'current-testing' or 'security-testing' "
                    f"for at least {MIN_AGE_DAYS} days."
                )
                raise PublishError(failure_msg)

            for build in self.parameters["build"]:
                build_bn = build.mangle()
                build_info = self.get_dist_artifacts_info(
                    stage="build", basename=build_bn
                )
                publish_info = self.get_dist_artifacts_info(
                    stage=stage, basename=build_bn
                )

                if not build_info:
                    raise PublishError(
                        f"{self.component}:{self.dist}:{build}: Cannot find build info."
                    )

                # If previous publication to a repo has been done and does not correspond to current
                # build artifacts, we delete previous publications. It happens if we modify local
                # sources and then publish into repository with the same version and release.
                info = build_info
                if publish_info:
                    if build_info["source-hash"] != publish_info["source-hash"]:
                        for repository in publish_info.get("repository-publish", []):
                            self.unpublish(
                                build=build,
                                sign_key=sign_key,
                                repository_publish=repository,
                            )
                    else:
                        info = publish_info

                self.publish(
                    build=build,
                    sign_key=sign_key,
                    db_path=db_path,
                    repository_publish=repository_publish,
                )

                self.create_metalink(repository_publish)

                # Save package information we published for committing into current
                info.setdefault("repository-publish", []).append(
                    {
                        "name": repository_publish,
                        "timestamp": datetime.utcnow().strftime("%Y%m%d%H%M"),
                    }
                )
                self.save_dist_artifacts_info(
                    stage="publish", basename=build_bn, info=info
                )

        if stage == "publish" and unpublish:
            if not all(
                self.is_published(
                    basename=build.mangle(), repository=repository_publish
                )
                for build in self.parameters["build"]
            ):
                log.info(
                    f"{self.component}:{self.dist}: Not published to '{repository_publish}'."
                )
                return

            for build in self.parameters["build"]:
                build_bn = build.mangle()
                publish_info = self.get_dist_artifacts_info(
                    stage=stage, basename=build_bn
                )

                self.unpublish(
                    build=build,
                    sign_key=sign_key,
                    repository_publish=repository_publish,
                )

                self.create_metalink(repository_publish)

                # Save package information we published for committing into current. If the packages
                # are not published into another repository, we delete the publish stage information.
                publish_info["repository-publish"] = [
                    r
                    for r in publish_info.get("repository-publish", [])
                    if r["name"] != repository_publish
                ]
                if publish_info.get("repository-publish", []):
                    self.save_dist_artifacts_info(
                        stage="publish", basename=build_bn, info=publish_info
                    )
                else:
                    log.info(
                        f"{self.component}:{self.dist}:{build_bn}: Not published anywhere else, deleting publish info."
                    )
                    self.delete_dist_artifacts_info(stage="publish", basename=build_bn)
