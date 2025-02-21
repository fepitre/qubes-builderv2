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
from typing import Optional

from qubesbuilder.distribution import QubesDistribution, DistributionError
from qubesbuilder.exc import TemplateError


class QubesTemplate:
    def __init__(self, template: dict):
        self.name = next(iter(template.keys()))
        if not self.name:
            raise TemplateError("Empty template.")

        template_desc = template[self.name]
        if not template_desc:
            raise TemplateError("Invalid value for template.")

        try:
            dist = template_desc.get("dist", None)
            if not dist or dist.startswith("host-"):
                raise TemplateError(
                    f"Invalid provided distribution for template '{self.name}'."
                )
            if not dist.startswith("vm-"):
                dist = f"vm-{dist}"
            self.distribution = QubesDistribution(dist)
        except DistributionError as e:
            raise TemplateError(str(e)) from e

        self.flavor = template_desc.get("flavor", "")
        self.options = template_desc.get("options", [])
        self.timestamp: Optional[str] = None
        self.timeout: int = template_desc.get("timeout", 3600)

    def to_str(self) -> str:
        return f"{self.name}"

    def __repr__(self):
        repr_str = self.to_str()
        if self.options:
            repr_str = f"{repr_str} (options: {','.join(self.options)})"
        return f"<QubesTemplate {repr_str}>"

    def __str__(self):
        return self.to_str()
