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
import re
import shutil
import urllib.parse
from pathlib import Path
from typing import Any

from qubesbuilder.component import QubesComponent
from qubesbuilder.executors import Executor, ExecutorError
from qubesbuilder.log import get_logger
from qubesbuilder.plugins import (
    ComponentPlugin,
    PluginError,
    BUILDER_DIR,
    PLUGINS_DIR,
)

log = get_logger("fetch")


class FetchError(PluginError):
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
        skip_git_fetch: bool = False,
        do_merge: bool = False,
        fetch_versions_only: bool = False,
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
        self.skip_git_fetch = skip_git_fetch
        self.do_merge = do_merge
        self.fetch_versions_only = fetch_versions_only

    def update_parameters(self):
        """
        Update plugin parameters based on component .qubesbuilder.
        """
        # Set and update parameters based on top-level "source"
        parameters = self.component.get_parameters(self._placeholders)
        self.parameters.update(parameters.get("source", {}))

    def run(self, stage: str):
        """
        Run plugin for given stage.
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
            copy_in = [(self.plugins_dir / "fetch", PLUGINS_DIR)]

            if local_source_dir.exists():
                # If we already fetched sources previously and have modified them,
                # we may want to keep local modifications.
                if not self.skip_if_exists:
                    shutil.rmtree(str(local_source_dir))
                else:
                    log.info(f"{self.component}: source already fetched. Updating.")
                    copy_in += [(local_source_dir, BUILDER_DIR)]

            # Get GIT source for a given Qubes OS component
            copy_out = [(source_dir, self.get_sources_dir())]
            get_sources_cmd = [
                str(PLUGINS_DIR / "fetch/scripts/get-and-verify-source"),
                "--component",
                self.component.name,
                "--git-branch",
                self.component.branch,
                "--git-url",
                self.component.url,
                "--keyring-dir-git",
                str(BUILDER_DIR / "keyring"),
                "--keys-dir",
                str(PLUGINS_DIR / "fetch/keys"),
            ]
            for maintainer in self.component.maintainers:
                get_sources_cmd += ["--maintainer", maintainer]
            if self.component.insecure_skip_checking:
                get_sources_cmd += ["--insecure-skip-checking"]
            if self.component.less_secure_signed_commits_sufficient:
                get_sources_cmd += ["--less-secure-signed-commits-sufficient"]

            # We prioritize do merge versions first
            if local_source_dir.exists() and self.do_merge:
                get_sources_cmd += ["--do-merge"]
                if self.fetch_versions_only:
                    get_sources_cmd += ["--fetch-versions-only"]
            if not self.skip_git_fetch:
                cmd = [f"cd {str(BUILDER_DIR)}", " ".join(get_sources_cmd)]
                self.executor.run(cmd, copy_in, copy_out, environment=self.environment)

            # Update parameters based on previously fetched sources as .qubesbuilder
            # is now available.
            self.update_parameters()

            distfiles_dir = self.get_distfiles_dir()
            distfiles_dir.mkdir(parents=True, exist_ok=True)

            # Download and verify files given in .qubesbuilder
            for file in self.parameters.get("files", []):
                parsed_url = urllib.parse.urlparse(file["url"])
                fn = str(os.path.basename(parsed_url.geturl()))

                # If we request to uncompress the file we drop the archive suffix
                if file.get("uncompress", False):
                    final_fn = Path(fn).with_suffix("").name
                else:
                    final_fn = fn

                if (distfiles_dir / final_fn).exists():
                    if not self.skip_if_exists:
                        os.remove(distfiles_dir / final_fn)
                    else:
                        log.info(
                            f"{self.component}: file {final_fn} already downloaded. Skipping."
                        )
                        continue
                copy_in = [
                    (self.plugins_dir / "fetch", PLUGINS_DIR),
                    (self.component.source_dir, BUILDER_DIR),
                ]
                copy_out = [(source_dir / final_fn, distfiles_dir)]
                # Build command for "download-and-verify-file". We let the script checking
                # necessary options.
                download_verify_cmd = [
                    str(PLUGINS_DIR / "fetch/scripts/download-and-verify-file"),
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
                    copy_out += [
                        (
                            BUILDER_DIR
                            / self.component.name
                            / os.path.basename(file["signature"]),
                            distfiles_dir,
                        )
                    ]
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

            artifacts_dir = self.get_component_artifacts_dir(stage)
            distfiles_dir = self.get_distfiles_dir()

            # Modules (formerly known as INCLUDED_SOURCES in Makefile.builder)
            modules = self.parameters.get("modules", [])

            # Source component directory inside executors
            source_dir = BUILDER_DIR / self.component.name

            # Clean previous build artifacts
            if artifacts_dir.exists():
                shutil.rmtree(artifacts_dir.as_posix())
            artifacts_dir.mkdir(parents=True)

            # We store the fetched source hash as original reference to be compared
            # for any further modifications. Once the source is fetched, we may locally
            # modify the source for development and at prep stage we would need to recompute
            # source hash based on those modifications.
            info: dict[str, Any] = {"source-hash": self.component.get_source_hash()}

            # Get git hash and tags
            copy_in = [
                (self.component.source_dir, BUILDER_DIR),
            ]
            copy_out = [
                (source_dir / "hash", artifacts_dir),
                (source_dir / "vtags", artifacts_dir),
            ]
            cmd = [
                f"rm -f {source_dir}/hash {source_dir}/vtags",
                f"cd {BUILDER_DIR}",
            ]
            cmd += [f"git -C {source_dir} rev-parse 'HEAD^{{}}' >> {source_dir}/hash"]
            cmd += [
                f"git -C {source_dir} tag --points-at HEAD --list 'v*' >> {source_dir}/vtags"
            ]
            try:
                self.executor.run(cmd, copy_in, copy_out, environment=self.environment)
            except ExecutorError as e:
                msg = f"{self.component}: Failed to get source hash information: {e}."
                raise FetchError(msg) from e

            # Read git hash and vtags
            with open(artifacts_dir / "hash") as f:
                data = f.read().splitlines()

            if not re.match(r"[\da-f]{7}", data[0]):
                msg = f"{self.component}: Invalid git hash detected."
                raise FetchError(msg)

            info["git-commit-hash"] = data[0]
            info["git-version-tags"] = []

            with open(artifacts_dir / "vtags") as f:
                data = f.read().splitlines()

            for tag in data:
                if not re.match("^v.*", tag):
                    msg = f"{self.component}: Invalid git version tag detected."
                    raise FetchError(msg)
                info["git-version-tags"].append(tag)

            if modules:
                # Get git module hashes
                copy_in = [
                    (self.component.source_dir, BUILDER_DIR),
                ]
                copy_out = [(source_dir / "modules", artifacts_dir)]
                cmd = [f"rm -f {source_dir}/modules", f"cd {BUILDER_DIR}"]
                for module in modules:
                    cmd += [
                        f"git -C {source_dir}/{module} rev-parse --short HEAD >> {source_dir}/modules"
                    ]
                try:
                    self.executor.run(
                        cmd, copy_in, copy_out, environment=self.environment
                    )
                except ExecutorError as e:
                    msg = f"{self.component}: Failed to get source module information: {str(e)}."
                    raise FetchError(msg) from e

                # Read package release name
                with open(artifacts_dir / "modules") as f:
                    data = f.read().splitlines()
                if len(data) != len(modules):
                    msg = f"{self.component}: Invalid modules data."
                    raise FetchError(msg)

                for commit_hash in data:
                    if not re.match("[0-9a-f]{7}", commit_hash):
                        msg = f"{self.component}: Invalid module hash detected."
                        raise FetchError(msg)

                info.update(
                    {
                        "modules": [
                            {"name": name, "hash": str(data[idx])}
                            for idx, name in enumerate(modules)
                        ],
                    }
                )

                copy_in = [
                    (distfiles_dir, BUILDER_DIR),
                    (self.component.source_dir, BUILDER_DIR),
                    (self.plugins_dir / "fetch", PLUGINS_DIR),
                ]
                copy_out = []
                cmd = []
                for module in info["modules"]:
                    module["archive"] = f"{module['name']}-{module['hash']}.tar.gz"
                    copy_out += [
                        (
                            source_dir / module["name"] / module["archive"],
                            distfiles_dir,
                        ),
                    ]
                    cmd += [
                        f"{PLUGINS_DIR}/fetch/scripts/create-archive {source_dir}/{module['name']} {module['archive']} {module['name']}/",
                    ]

                try:
                    self.executor.run(
                        cmd, copy_in, copy_out, environment=self.environment
                    )
                except ExecutorError as e:
                    msg = f"{self.component}: Failed to generate module archives: {str(e)}."
                    raise FetchError(msg) from e

            try:
                self.save_artifacts_info(stage=stage, basename="source", info=info)
                # Clean previous text files as all info are stored inside info
                os.remove(artifacts_dir / f"hash")
                os.remove(artifacts_dir / f"vtags")
                if modules:
                    os.remove(artifacts_dir / f"modules")
            except OSError as e:
                msg = f"{self.component}: Failed to clean artifacts: {str(e)}."
                raise FetchError(msg) from e
