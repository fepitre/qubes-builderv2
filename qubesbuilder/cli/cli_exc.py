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

"""
QubesBuilder command-line interface - exceptions module.
"""

from typing import Optional, IO

import click

from qubesbuilder.exc import QubesBuilderError
from qubesbuilder.log import QubesBuilderLogger


class CliError(QubesBuilderError, click.ClickException):
    """
    An exception that Click can handle and show to the user.
    """

    def show(self, file: Optional[IO] = None) -> None:
        QubesBuilderLogger.critical(self.format_message())
