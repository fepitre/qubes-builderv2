from qubesbuilder.common import is_filename_valid


def test_filename():
    assert is_filename_valid("xfwm4_4.14.2.orig.tar.bz2")
    assert not is_filename_valid("xfwm4_4$14.2.orig@tar.bz2")
    assert not is_filename_valid("-xfwm4_4.14.2.orig.tar.bz2")
