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

from abc import ABC, abstractmethod
from pathlib import Path

from qubesbuilder.exc import QubesBuilderError
from qubesbuilder.log import get_logger

log = get_logger("executor")


class ExecutorError(QubesBuilderError):
    """
    Base executor exception
    """

    pass


class Executor(ABC):
    """
    Base executor class
    """

    _builder_dir = Path("/builder")

    def get_builder_dir(self):
        return self._builder_dir

    def get_build_dir(self):
        return self.get_builder_dir() / "build"

    def get_plugins_dir(self):
        return self.get_builder_dir() / "plugins"

    def get_distfiles_dir(self):
        return self.get_builder_dir() / "distfiles"

    def get_repository_dir(self):
        return self.get_builder_dir() / "repository"

    def get_cache_dir(self):
        return self.get_builder_dir() / "cache"

    @abstractmethod
    def copy_in(self, *args, **kwargs):
        pass

    @abstractmethod
    def copy_out(self, *args, **kwargs):
        pass

    @abstractmethod
    def run(self, *args, **kwargs):
        pass
