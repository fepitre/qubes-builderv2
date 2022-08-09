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

from pathlib import Path

from qubesbuilder.template import QubesTemplate
from qubesbuilder.executors import Executor
from qubesbuilder.log import get_logger
from qubesbuilder.plugins.template import TemplateBuilderPlugin

log = get_logger("template_debian")


class DEBTemplateBuilderPlugin(TemplateBuilderPlugin):
    """
    RPMTemplatePlugin manages RPM distributions build.
    """

    def __init__(
        self,
        template: QubesTemplate,
        executor: Executor,
        plugins_dir: Path,
        artifacts_dir: Path,
        qubes_release: str,
        gpg_client: str,
        sign_key: dict,
        repository_publish: dict,
        repository_upload_remote_host: dict,
        min_age_days: int,
        verbose: bool = False,
        debug: bool = False,
        use_qubes_repo: dict = None,
    ):
        super().__init__(
            template=template,
            executor=executor,
            plugins_dir=plugins_dir,
            artifacts_dir=artifacts_dir,
            qubes_release=qubes_release,
            gpg_client=gpg_client,
            sign_key=sign_key,
            repository_publish=repository_publish,
            repository_upload_remote_host=repository_upload_remote_host,
            use_qubes_repo=use_qubes_repo,
            verbose=verbose,
            debug=debug,
            min_age_days=min_age_days,
        )

        # The parent class will automatically copy-in all its plugin dependencies. Calling parent
        # class method (for generic steps), we need to have access to this plugin dependencies.
        self.plugin_dependencies += ["template_debian", "build_deb"]

        self.environment.update(
            {
                "TEMPLATE_CONTENT_DIR": str(
                    self.executor.get_plugins_dir() / "template_debian"
                )
            }
        )

    def run(
        self,
        stage: str,
        *args,
        repository_publish: str = None,
        ignore_min_age: bool = False,
        unpublish: bool = False,
        **kwargs,
    ):
        super().run(
            stage=stage,
            repository_publish=repository_publish,
            ignore_min_age=ignore_min_age,
            unpublish=unpublish,
            **kwargs,
        )
