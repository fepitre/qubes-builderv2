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

import re

from qubesbuilder.exc import DistributionError

FEDORA_RE = re.compile("^fc([0-9]+)$")
CENTOS_STREAM_RE = re.compile("^centos-stream([0-9]+)$")

DEBIAN = {
    "stretch": "9",
    "buster": "10",
    "bullseye": "11",
    "bookworm": "12",
    "trixie": "13",
}

DEBIAN_ARCHITECTURE = {"x86_64": "amd64", "ppc64le": "ppc64el"}


class QubesDistribution:
    def __init__(self, distribution: str):
        self.distribution = distribution
        self.package_set, self.name = distribution.split("-", 1)
        if self.name == self.name.split(".")[0]:
            self.architecture = "x86_64"
        else:
            self.name, self.architecture = self.name.split(".", 1)
        if self.package_set not in ("host", "vm"):
            raise DistributionError(f"Unknown package set '{self.package_set}'")

        self.version = None
        is_fedora = FEDORA_RE.match(self.name)
        is_centos_stream = CENTOS_STREAM_RE.match(self.name)
        is_debian = DEBIAN.get(self.name, None)
        if is_fedora:
            self.fullname = "fedora"
            self.version = is_fedora.group(1)
            self.tag = self.name
            self.family = "rpm"
        elif is_centos_stream:
            self.fullname = "centos-stream"
            self.version = is_centos_stream.group(1)
            self.tag = f"el{self.version}"
            self.family = "rpm"
        elif is_debian:
            self.fullname = "debian"
            self.version = DEBIAN[self.name]
            self.architecture = DEBIAN_ARCHITECTURE.get(
                self.architecture, self.architecture
            )
            self.tag = f"deb{self.version}"
            self.family = "deb"
        else:
            raise DistributionError(f"Unsupported distribution '{self.distribution}'")

    def to_str(self) -> str:
        return f"{self.package_set}-{self.fullname}-{self.version}.{self.architecture}"

    def __repr__(self):
        return f"<QubesDistribution {self.to_str()}>"

    def __str__(self):
        return self.to_str()

    def __eq__(self, other):
        return repr(self) == repr(other)

    def is_rpm(self) -> bool:
        if FEDORA_RE.match(self.name) or CENTOS_STREAM_RE.match(self.name):
            return True
        return False

    def is_deb(self) -> bool:
        if DEBIAN.get(self.name, None):
            return True
        return False
