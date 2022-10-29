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

from qubesbuilder.config import Config
from qubesbuilder.pluginmanager import PluginManager
from qubesbuilder.log import get_logger
from qubesbuilder.plugins.template import TemplateBuilderPlugin
from qubesbuilder.template import QubesTemplate

log = get_logger("template_rpm")


class RPMTemplateBuilderPlugin(TemplateBuilderPlugin):
    """
    RPMTemplatePlugin manages RPM distributions build.
    """

    @classmethod
    def supported_template(cls, template: QubesTemplate):
        return template.distribution.is_rpm()

    def __init__(
        self, template: QubesTemplate, config: Config, manager: PluginManager, **kwargs
    ):
        super().__init__(template=template, config=config, manager=manager)

        # The parent class will automatically copy-in all its plugin dependencies. Calling parent
        # class method (for generic steps), we need to have access to this plugin dependencies.
        self.dependencies += ["template_rpm"]

    def update_parameters(self, stage: str):
        super().update_parameters(stage)
        executor = self.config.get_executor_from_config(stage_name=stage)

        self.environment.update(
            {"TEMPLATE_CONTENT_DIR": str(executor.get_plugins_dir() / "template_rpm")}
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

        self.files_inside_executor_with_placeholders.append(
            "@PLUGINS_DIR@/template_rpm/04_install_qubes.sh"
        )


TEMPLATE_PLUGINS = [RPMTemplateBuilderPlugin]
