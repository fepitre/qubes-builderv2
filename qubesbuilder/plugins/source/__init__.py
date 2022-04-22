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

import os.path
import shutil
import urllib.parse
from pathlib import Path

from qubesbuilder.component import QubesComponent
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.executors import Executor
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import (
    ComponentPlugin,
    DistributionPlugin,
    PluginError,
    BUILDER_DIR,
    PLUGINS_DIR,
)

log = get_logger("source")


def _get_distfile_fname(file: dict):
    """
    Return downloaded file nd expected distfile filenames. If 'uncompress'
     is not requested, both filenames are the same.
    """
    if file.get("name"):
        fn = file["name"]
    else:
        # Fallback method for determining downloaded file name. This is fragile if
        # the url does not provide it (e.g. downloading archive from github commit)
        parsed_url = urllib.parse.urlparse(file["url"])
        fn = os.path.basename(parsed_url.geturl())

    # If we request to uncompress the file we drop the archive suffix
    if file.get("uncompress", False):
        final_fn = Path(fn).with_suffix("").name
    else:
        final_fn = fn
    return fn, final_fn


class SourceError(PluginError):
    pass


class FetchPlugin(ComponentPlugin):
    """
    Manage generic fetch source

    Stages:
        - fetch: Downloads and verify external files
    """

    def __init__(
        self,
        component: QubesComponent,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        verbose: bool = False,
        debug: bool = False,
        skip_if_exists: bool = False,
    ):
        super().__init__(
            component=component,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            verbose=verbose,
            debug=debug,
        )
        self.executor = executor
        self.skip_if_exists = skip_if_exists

    def update_parameters(self):
        """
        Update plugin parameters based on component .qubesbuilder.
        """
        # Set and update parameters based on top-level "source"
        parameters = self.component.get_parameters(self._placeholders)
        self.parameters.update(parameters.get("source", {}))

    def run(self, stage: str):
        """
        Run plugging for given stage.
        """
        # Run stage defined by parent class
        super().run(stage=stage)

        # Source component directory
        local_source_dir = self.get_sources_dir() / self.component.name
        # Ensure "artifacts/sources" directory exists
        self.get_sources_dir().mkdir(parents=True, exist_ok=True)

        if stage == "fetch":
            # Source component directory inside executors
            source_dir = BUILDER_DIR / self.component.name

            if local_source_dir.exists():
                # If we already fetched sources previously and have modified them,
                # we may want to keep local modifications.
                if not self.skip_if_exists:
                    shutil.rmtree(str(local_source_dir))
                else:
                    log.info(f"{self.component}: source already fetched. Skipping.")

            if not local_source_dir.exists():
                # Get GIT source for a given Qubes OS component
                copy_in = [(self.plugins_dir / "source", PLUGINS_DIR)]
                copy_out = [(source_dir, self.get_sources_dir())]
                get_sources_cmd = [
                    str(PLUGINS_DIR / "source/scripts/get-and-verify-source"),
                    "--component",
                    self.component.name,
                    "--git-branch",
                    self.component.branch,
                    "--git-url",
                    self.component.url,
                    "--keyring-dir-git",
                    str(BUILDER_DIR / "keyring"),
                    "--keys-dir",
                    str(PLUGINS_DIR / "source/keys"),
                ]
                for maintainer in self.component.maintainers:
                    get_sources_cmd += ["--maintainer", maintainer]
                if self.component.insecure_skip_checking:
                    get_sources_cmd += ["--insecure-skip-checking"]
                if self.component.less_secure_signed_commits_sufficient:
                    get_sources_cmd += ["--less-secure-signed-commits-sufficient"]
                cmd = [f"cd {str(BUILDER_DIR)}", " ".join(get_sources_cmd)]
                self.executor.run(cmd, copy_in, copy_out, environment=self.environment)

            # Update parameters based on previously fetched sources as .qubesbuilder
            # is now available.
            self.update_parameters()

            distfiles_dir = self.get_distfiles_dir()
            distfiles_dir.mkdir(parents=True, exist_ok=True)

            # Download and verify files given in .qubesbuilder
            for file in self.parameters.get("files", []):
                fn, distfile_fn = _get_distfile_fname(file)

                if (distfiles_dir / distfile_fn).exists():
                    if not self.skip_if_exists:
                        os.remove(distfiles_dir / distfile_fn)
                    else:
                        log.info(
                            f"{self.component}: file {distfile_fn} already downloaded. Skipping."
                        )
                        continue
                copy_in = [
                    (self.plugins_dir / "source", PLUGINS_DIR),
                    (self.component.source_dir, BUILDER_DIR),
                ]
                copy_out = [(source_dir / distfile_fn, distfiles_dir)]
                # Build command for "download-and-verify-file". We let the script checking
                # necessary options.
                download_verify_cmd = [
                    str(PLUGINS_DIR / "source/scripts/download-and-verify-file"),
                    "--output-dir",
                    str(BUILDER_DIR / self.component.name),
                    "--file-name",
                    fn,
                    "--file-url",
                    file["url"],
                ]
                if file.get("sha256", None):
                    download_verify_cmd += [
                        "--checksum-cmd",
                        "sha256sum",
                        "--checksum-file",
                        str(BUILDER_DIR / self.component.name / file["sha256"]),
                    ]
                elif file.get("sha512", None):
                    download_verify_cmd += [
                        "--checksum-cmd",
                        "sha512sum",
                        "--checksum-file",
                        str(BUILDER_DIR / self.component.name / file["sha512"]),
                    ]
                if file.get("signature", None):
                    download_verify_cmd += ["--signature-url", file["signature"]]
                if file.get("pubkeys", None):
                    for pubkey in file["pubkeys"]:
                        download_verify_cmd += ["--pubkey-file", pubkey]
                if file.get("uncompress", False):
                    download_verify_cmd += ["--uncompress"]
                cmd = [
                    f"cd {str(BUILDER_DIR / self.component.name)}",
                    " ".join(download_verify_cmd),
                ]
                self.executor.run(cmd, copy_in, copy_out, environment=self.environment)


class SourcePlugin(DistributionPlugin):
    """
    Manage generic distribution source
    """

    def __init__(
        self,
        component: QubesComponent,
        dist: QubesDistribution,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        backend_vmm: str,
        verbose: bool = False,
        debug: bool = False,
        skip_if_exists: bool = False,
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
        self.skip_if_exists = skip_if_exists

        # Set and update parameters based on top-level "source",
        # per package set and per distribution.
        parameters = self.component.get_parameters(self._placeholders)

        self.parameters.update(parameters.get("source", {}))
        self.parameters.update(
            parameters.get(self.dist.package_set, {}).get("source", {})
        )
        self.parameters.update(
            parameters.get(self.dist.distribution, {}).get("source", {})
        )

    @staticmethod
    def get_distfile_fname(file: dict):
        return _get_distfile_fname(file)
