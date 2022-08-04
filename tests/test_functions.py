import pytest

from qubesbuilder.common import is_filename_valid, deep_check


def test_filename():
    assert is_filename_valid("xfwm4_4.14.2.orig.tar.bz2")
    assert not is_filename_valid("xfwm4_4$14.2.orig@tar.bz2")
    assert not is_filename_valid("-xfwm4_4.14.2.orig.tar.bz2")


def test_qubesbuilder_data():
    data = {
        "host": {"rpm": {"build": ["python-qasync.spec"]}},
        "vm": {
            "rpm": {"build": ["python-qasync.spec"]},
            "deb": {"build": ["debian-pkg/debian"]},
        },
        "source": {
            "files": [
                {
                    "url": "https://files.pythonhosted.org/packages/source/q/qasync/qasync-0.23.0.tar.gz",
                    "sha256": "qasync-0.23.0.tar.gz.sha256",
                }
            ]
        },
    }
    deep_check(data)

    data = {"a": "../.."}
    with pytest.raises(ValueError) as e:
        deep_check(data)
    assert ".." in e.value.args[0]

    data = {"..": "b"}
    with pytest.raises(ValueError) as e:
        deep_check(data)
    assert ".." in e.value.args[0]

    data = {"a": {"b": ["c", "d", {"e": "toto.build.yml"}]}}
    with pytest.raises(ValueError) as e:
        deep_check(data)
    assert ".build.yml" in e.value.args[0]

    data = {
        "host": {"rpm": {"build": ["python-qasync.spec"]}},
        "vm": {
            "rpm": {"build": ["python-qasync.spec"]},
            "deb": {"build": ["debian-pkg/debian"]},
        },
        "source": {
            "files": [
                {
                    "url": "https://files.pythonhosted.org/packages/source/q/qasync/qasync-0.23.0.tar.gz",
                    "sha256": "qasync-0.23.0.tar.gz.sha256",
                },
                {
                    "url": "https://malicious/url/../toto.tar.gz",
                    "sha256": "toto.tar.gz.sha256",
                },
            ]
        },
    }
    with pytest.raises(ValueError) as e:
        deep_check(data)
    assert ".." in e.value.args[0]

    data = {
        "host": {"rpm": {"build": ["python-qasync.spec"]}},
        "vm": {
            "rpm": {"build": ["python-qasync.spec"]},
            "deb": {"build": ["python-qasync.spec.fetch.yaml"]},
        },
        "source": {
            "files": [
                {
                    "url": "https://files.pythonhosted.org/packages/source/q/qasync/qasync-0.23.0.tar.gz",
                    "sha256": "qasync-0.23.0.tar.gz.sha256",
                },
            ]
        },
    }
    with pytest.raises(ValueError) as e:
        deep_check(data)
    assert ".fetch.yaml" in e.value.args[0]
