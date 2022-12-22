import os.path
import tempfile

import pytest

from qubesbuilder.common import VerificationMode
from qubesbuilder.component import QubesComponent
from qubesbuilder.config import Config
from qubesbuilder.distribution import QubesDistribution
from qubesbuilder.template import QubesTemplate
from qubesbuilder.exc import ComponentError, DistributionError, ConfigError
from qubesbuilder.plugins import DistributionComponentPlugin
from qubesbuilder.pluginmanager import PluginManager

#
# QubesComponent
#


def test_component():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/rel", "w") as f:
            f.write("4")
        with open(f"{source_dir}/.qubesbuilder", "w") as f:
            f.write("")
        component = QubesComponent(source_dir)
        component.get_parameters()

        assert component.version == "1.2.3"
        assert component.release == "4"

        repr_str = f"<QubesComponent {os.path.basename(source_dir)}>"
        assert component.to_str() == os.path.basename(source_dir)
        assert str(component) == os.path.basename(source_dir)
        assert repr(component) == repr_str


def test_component_rc():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3-rc5")
        with open(f"{source_dir}/rel", "w") as f:
            f.write("4.1")
        with open(f"{source_dir}/.qubesbuilder", "w") as f:
            f.write("")
        component = QubesComponent(source_dir)
        component.get_parameters()

        assert component.version == "1.2.3-rc5"
        assert component.release == "4.1"

        repr_str = f"<QubesComponent {os.path.basename(source_dir)}>"
        assert component.to_str() == os.path.basename(source_dir)
        assert str(component) == os.path.basename(source_dir)
        assert repr(component) == repr_str


def test_component_no_qubesbuilder():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/rel", "w") as f:
            f.write("4")
        with pytest.raises(ComponentError) as e:
            QubesComponent(source_dir).get_parameters()
        msg = f"Cannot find '.qubesbuilder' in {source_dir}."
        assert str(e.value) == msg


def test_component_no_source():
    with tempfile.TemporaryDirectory():
        with pytest.raises(ComponentError) as e:
            QubesComponent("/does/not/exist").get_parameters()
        msg = f"Cannot find source directory /does/not/exist."
        assert str(e.value) == msg


def test_component_no_version():
    with tempfile.TemporaryDirectory() as source_dir:
        with pytest.raises(ComponentError) as e:
            QubesComponent(source_dir).get_parameters()
        msg = f"Cannot determine version for {source_dir}."
        assert str(e.value) == msg


def test_component_invalid_version():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("wrongversion")
        with pytest.raises(ComponentError) as e:
            QubesComponent(source_dir).get_parameters()
        msg = f"Invalid version for {source_dir}."
        assert str(e.value) == msg


def test_component_no_release():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/.qubesbuilder", "w") as f:
            f.write("")
        component = QubesComponent(source_dir)
        component.get_parameters()
        assert component.version == "1.2.3"
        assert component.release == "1"


def test_component_invalid_release():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/rel", "w") as f:
            f.write("wrongrelease")
        with pytest.raises(ComponentError) as e:
            QubesComponent(source_dir).get_parameters()
        msg = f"Invalid release for {source_dir}."
        assert str(e.value) == msg


def test_component_invalid_release2():
    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/rel", "w") as f:
            # only one decimal point allowed
            f.write("3.2.1")
        with pytest.raises(ComponentError) as e:
            QubesComponent(source_dir).get_parameters()
        msg = f"Invalid release for {source_dir}."
        assert str(e.value) == msg


def test_component_no_packages_1():
    manager = PluginManager([])
    fcdist = QubesDistribution("vm-fc42")
    debdist = QubesDistribution("vm-bullseye")

    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write("{}")
        config_file.flush()
        config = Config(config_file.name)

    with tempfile.TemporaryDirectory() as source_dir:
        with open(f"{source_dir}/version", "w") as f:
            f.write("1.2.3")
        with open(f"{source_dir}/rel", "w") as f:
            f.write("1")

        # no .qubesbuilder
        component = QubesComponent(source_dir, has_packages=False)

        plugin = DistributionComponentPlugin(
            component=component, dist=fcdist, config=config, manager=manager
        )
        assert not plugin.has_component_packages(stage="prep")

        # .qubesbuilder
        with open(f"{source_dir}/.qubesbuilder", "w") as f:
            f.write(
                """
vm:
  rpm:
    build:
      - toto.spec
"""
            )

        component = QubesComponent(source_dir)

        # build for RPM
        plugin = DistributionComponentPlugin(
            component=component, dist=fcdist, config=config, manager=manager
        )
        assert plugin.has_component_packages(stage="prep")

        # no build for DEB
        plugin = DistributionComponentPlugin(
            component=component, dist=debdist, config=config, manager=manager
        )
        assert not plugin.has_component_packages(stage="prep")


#
# QubesDistribution
#


def test_dist():
    dist = QubesDistribution("vm-fc42")
    assert dist.version == "42"
    assert dist.fullname == "fedora"
    assert dist.architecture == "x86_64"
    assert dist.tag == "fc42"

    repr_str = "<QubesDistribution vm-fedora-42.x86_64>"
    assert dist.to_str() == "vm-fedora-42.x86_64"
    assert str(dist) == "vm-fedora-42.x86_64"
    assert repr(dist) == repr_str

    dist = QubesDistribution("vm-trixie")
    assert dist.version == "13"
    assert dist.fullname == "debian"
    assert dist.architecture == "amd64"

    repr_str = "<QubesDistribution vm-debian-13.amd64>"
    assert dist.to_str() == "vm-debian-13.amd64"
    assert str(dist) == "vm-debian-13.amd64"
    assert repr(dist) == repr_str


def test_dist_non_default_arch():
    dist = QubesDistribution("vm-fc42.ppc64le")
    assert dist.version == "42"
    assert dist.fullname == "fedora"
    assert dist.architecture == "ppc64le"
    assert dist.tag == "fc42"

    repr_str = "<QubesDistribution vm-fedora-42.ppc64le>"
    assert dist.to_str() == "vm-fedora-42.ppc64le"
    assert str(dist) == "vm-fedora-42.ppc64le"
    assert repr(dist) == repr_str

    dist = QubesDistribution("vm-trixie.ppc64el")
    assert dist.version == "13"
    assert dist.fullname == "debian"
    assert dist.architecture == "ppc64el"

    repr_str = "<QubesDistribution vm-debian-13.ppc64el>"
    assert dist.to_str() == "vm-debian-13.ppc64el"
    assert str(dist) == "vm-debian-13.ppc64el"
    assert repr(dist) == repr_str


def test_dist_unknown_package_set():
    with pytest.raises(DistributionError) as e:
        QubesDistribution("notset-fc42")

    msg = "Unknown package set 'notset'"
    assert str(e.value) == msg


def test_dist_unknown():
    with pytest.raises(DistributionError) as e:
        QubesDistribution("host-lfs")
    msg = "Unsupported distribution 'host-lfs'"
    assert str(e.value) == msg


def test_dist_family():
    assert QubesDistribution("vm-fc42").is_rpm()
    assert QubesDistribution("host-bookworm").is_deb()
    assert not QubesDistribution("host-centos-stream9").is_deb()


#
# QubesTemplate
#


def test_template():
    template = QubesTemplate(
        {
            "fedora-42-xfce": {
                "dist": "vm-fc42",
                "flavor": "notset",
                "options": ["no-recommends", "hardened"],
            }
        }
    )
    assert template.distribution.fullname == "fedora"
    assert template.distribution.version == "42"
    assert template.distribution.package_set == "vm"

    repr_str = "<QubesTemplate fedora-42-xfce (options: no-recommends,hardened)>"
    assert template.to_str() == "fedora-42-xfce"
    assert str(template) == "fedora-42-xfce"
    assert repr(template) == repr_str


def test_config_verification():
    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """components:
 - example:
     verification-mode: less-secure-signed-commits-sufficient
"""
        )
        config_file.flush()
        config = Config(config_file.name)
        component = config.get_components(["example"])[0]
        assert component.verification_mode == VerificationMode.SignedCommit

    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """components:
 - example:
     verification-mode: insecure-skip-checking
"""
        )
        config_file.flush()
        config = Config(config_file.name)
        component = config.get_components(["example"])[0]
        assert component.verification_mode == VerificationMode.Insecure

    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """
less-secure-signed-commits-sufficient:
 - example
components:
 - example
"""
        )
        config_file.flush()
        config = Config(config_file.name)
        component = config.get_components(["example"])[0]
        assert component.verification_mode == VerificationMode.SignedCommit

    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """
components:
 - example
"""
        )
        config_file.flush()
        config = Config(config_file.name)
        component = config.get_components(["example"])[0]
        assert component.verification_mode == VerificationMode.SignedTag


def test_config_fetch_versions_only():
    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """components:
 - example:
     fetch-versions-only: True
"""
        )
        config_file.flush()
        config = Config(config_file.name)
        component = config.get_components(["example"])[0]
        assert component.fetch_versions_only == True

    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """
fetch-versions-only: True
components:
 - example:
     fetch-versions-only: False
"""
        )
        config_file.flush()
        config = Config(config_file.name)
        component = config.get_components(["example"])[0]
        assert component.fetch_versions_only == False

    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """
fetch-versions-only: True
components:
 - example
"""
        )
        config_file.flush()
        config = Config(config_file.name)
        component = config.get_components(["example"])[0]
        assert component.fetch_versions_only == True

    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """
components:
 - example
"""
        )
        config_file.flush()
        config = Config(config_file.name)
        component = config.get_components(["example"])[0]
        assert component.fetch_versions_only == False


def test_config_components_filter():
    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """components:
 - component1
 - component2
 - component3:
     # same repo as component1, but different branch
     url: https://github.com/QubesOS/qubes-component1
     branch: another
"""
        )
        config_file.flush()
        config = Config(config_file.name)

        assert [c.name for c in config.get_components()] == [
            "component1",
            "component2",
            "component3",
        ]
        assert [c.name for c in config.get_components(["component2"])] == ["component2"]
        assert [c.name for c in config.get_components(["component1"])] == ["component1"]
        assert [c.name for c in config.get_components(["component1"], True)] == [
            "component1",
            "component3",
        ]
        assert [c.name for c in config.get_components(["component3"])] == ["component3"]
        with pytest.raises(ConfigError):
            config.get_components(["no-such-component"])


def test_config_distributions_filter():
    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """distributions:
 - vm-fc36
 - vm-bullseye
 - host-fc37
"""
        )
        config_file.flush()
        config = Config(config_file.name)

        assert [d.distribution for d in config.get_distributions()] == [
            "vm-fc36",
            "vm-bullseye",
            "host-fc37",
        ]
        assert [d.distribution for d in config.get_distributions(["vm-fc36"])] == [
            "vm-fc36"
        ]
        assert [
            d.distribution for d in config.get_distributions(["vm-fc36", "host-fc37"])
        ] == [
            "vm-fc36",
            "host-fc37",
        ]
        with pytest.raises(ConfigError):
            config.get_distributions(["vm-fc32"])


def test_config_templates_filter():
    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """templates:
  - fedora-36-xfce:
      dist: fc36
      flavor: xfce
  - centos-stream-8:
      dist: centos-stream8
  - debian-11:
      dist: bullseye
      options:
        - standard
        - firmware
"""
        )
        config_file.flush()
        config = Config(config_file.name)

        assert [t.name for t in config.get_templates()] == [
            "fedora-36-xfce",
            "centos-stream-8",
            "debian-11",
        ]
        assert [t.name for t in config.get_templates(["debian-11"])] == ["debian-11"]
        assert [
            t.name for t in config.get_templates(["fedora-36-xfce", "debian-11"])
        ] == [
            "fedora-36-xfce",
            "debian-11",
        ]
        with pytest.raises(ConfigError):
            config.get_templates(["fedora-32"])


def test_config_options():
    with tempfile.NamedTemporaryFile("w") as config_file:
        config_file.write(
            """components:
 - lvm2
 - kernel

force-fetch: false

executor:
  type: podman
  options:
    image: myimage
    something: else
"""
        )
        config_file.flush()
        options = {
            "+components": [{"kernel": {"branch": "stable-5.15"}}],
            "force-fetch": True,
            "executor": {"options": {"image": "fedora"}},
        }
        config = Config(config_file.name, options)
        component = config.get_components(["kernel"])[0]
        assert component.branch == "stable-5.15"
        assert config.force_fetch == True
        assert config.get("executor").get("options").get("image") == "fedora"
