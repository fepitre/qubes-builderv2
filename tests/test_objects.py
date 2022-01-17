import os.path
import tempfile

import pytest

from qubesbuilder.component import Component
from qubesbuilder.dist import Dist
from qubesbuilder.exc import ComponentException, DistException


#
# Component
#


def test_component():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/rel", "w") as f:
            f.write("4")
        with open(f"{source_dir}/.qubesbuilder", "w") as f:
            f.write("")
        component = Component(source_dir)
        component.get_parameters()

        assert component.version == "1.2.3"
        assert component.release == "4"

        repr_str = f"<Component {os.path.basename(source_dir)}>"
        assert component.to_str() == os.path.basename(source_dir)
        assert str(component) == os.path.basename(source_dir)
        assert repr(component) == repr_str


def test_component_no_qubesbuilder():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/rel", "w") as f:
            f.write("4")
        with pytest.raises(ComponentException) as e:
            Component(source_dir).get_parameters()
        msg = f"Cannot find '.qubesbuilder' in {source_dir}"
        assert str(e.value) == msg


def test_component_no_source():
    with tempfile.TemporaryDirectory():
        with pytest.raises(ComponentException) as e:
            Component("/does/not/exist").get_parameters()
        msg = f"Cannot find source directory /does/not/exist"
        assert str(e.value) == msg


def test_component_no_version():
    with tempfile.TemporaryDirectory() as source_dir:
        with pytest.raises(ComponentException) as e:
            Component(source_dir).get_parameters()
        msg = f"Cannot find version file in {source_dir}"
        assert str(e.value) == msg


def test_component_invalid_version():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("wrongversion")
        with pytest.raises(ComponentException) as e:
            Component(source_dir).get_parameters()
        msg = f"Invalid version for {source_dir}"
        assert str(e.value) == msg


def test_component_no_release():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/.qubesbuilder", "w") as f:
            f.write("")
        component = Component(source_dir)
        component.get_parameters()
        assert component.version == "1.2.3"
        assert component.release == "1"


def test_component_invalid_release():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/rel", "w") as f:
            f.write("wrongrelease")
        with pytest.raises(ComponentException) as e:
            Component(source_dir).get_parameters()
        msg = f"Invalid release for {source_dir}"
        assert str(e.value) == msg


#
# Dist
#


def test_dist():
    dist = Dist("vm-fc42")
    assert dist.version == "42"
    assert dist.fullname == "fedora"
    assert dist.architecture == "x86_64"
    assert dist.tag == "fc42"

    repr_str = "<Dist vm-fedora-42.x86_64>"
    assert dist.to_str() == "vm-fedora-42.x86_64"
    assert str(dist) == "vm-fedora-42.x86_64"
    assert repr(dist) == repr_str

    dist = Dist("vm-trixie")
    assert dist.version == "13"
    assert dist.fullname == "debian"
    assert dist.architecture == "amd64"

    repr_str = "<Dist vm-debian-13.amd64>"
    assert dist.to_str() == "vm-debian-13.amd64"
    assert str(dist) == "vm-debian-13.amd64"
    assert repr(dist) == repr_str


def test_dist_non_default_arch():
    dist = Dist("vm-fc42.ppc64le")
    assert dist.version == "42"
    assert dist.fullname == "fedora"
    assert dist.architecture == "ppc64le"
    assert dist.tag == "fc42"

    repr_str = "<Dist vm-fedora-42.ppc64le>"
    assert dist.to_str() == "vm-fedora-42.ppc64le"
    assert str(dist) == "vm-fedora-42.ppc64le"
    assert repr(dist) == repr_str

    dist = Dist("vm-trixie.ppc64el")
    assert dist.version == "13"
    assert dist.fullname == "debian"
    assert dist.architecture == "ppc64el"

    repr_str = "<Dist vm-debian-13.ppc64el>"
    assert dist.to_str() == "vm-debian-13.ppc64el"
    assert str(dist) == "vm-debian-13.ppc64el"
    assert repr(dist) == repr_str


def test_dist_unknown_package_set():
    with pytest.raises(DistException) as e:
        Dist("notset-fc42")

    msg = "Unknown package set 'notset'"
    assert str(e.value) == msg


def test_dist_unknown():
    with pytest.raises(DistException) as e:
        Dist("host-lfs")
    msg = "Unsupported distribution"
    assert str(e.value) == msg


def test_dist_family():
    assert Dist("vm-fc42").is_rpm()
    assert Dist("host-bookworm").is_deb()
    assert Dist("vm-whonix-gw-16").is_deb()
    assert not Dist("vm-whonix-gw-16").is_rpm()
    assert not Dist("host-centos-stream9").is_deb()
