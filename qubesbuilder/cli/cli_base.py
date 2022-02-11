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
QubesBuilder command-line interface - base module.
"""

import sys
import traceback
from typing import Callable

import click

from qubesbuilder.config import Config


class ContextObj:
    """
    Helper object for keeping state in :attr:`click.Context.obj`
    """

    def __init__(self, config: Config):
        self.config = config
        self.components = None
        self.distributions = None
        self.templates = None


class AliasedGroup(click.Group):
    """
    A very simple alias engine for :class:`click.Group`
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.aliases = {}
        self.debug = False

    def __call__(self, *args, **kwargs):
        try:
            return self.main(*args, **kwargs)
        except Exception as exc:
            click.secho(f'Error: {exc}', fg="red")
            if self.debug is True:
                traceback.print_exception(*sys.exc_info())

            if isinstance(exc, click.ClickException):
                # pylint: disable=no-member
                sys.exit(exc.exit_code)
            else:
                sys.exit(1)

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail(f"Too many matches: {', '.join(sorted(matches))}")

    def resolve_command(self, ctx, args):
        _, cmd, args = super().resolve_command(ctx, args)
        return cmd.name if cmd else None, cmd, args

    def add_alias(self, **kwargs):
        """
        Add aliases to a command

        >>> cmd.add_alias(alias='original-command')
        """
        assert all(alias not in (*self.aliases, *self.commands) for alias in kwargs)
        self.aliases.update(kwargs)


def aliased_group(name=None, **kwargs) -> Callable[[Callable], AliasedGroup]:
    """
    A decorator that creates an AliasedGroup.
    """

    def decorator(f):
        return click.group(name, cls=AliasedGroup, **kwargs)(f)

    return decorator
