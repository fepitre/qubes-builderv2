ifeq ($(DISTRIBUTION),)
    $(warning This plugin must be loaded after distribution-specifc one)
else ifneq (,$(findstring $(DISTRIBUTION), debian qubuntu fedora centos centos-stream archlinux))
ifeq (,$(GITHUB_STATE_DIR))
    $(error GITHUB_STATE_DIR not set)
endif
    BUILDER_GITHUB_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))
    BUILDER_MAKEFILE += $(BUILDER_GITHUB_DIR)/Makefile.github
else
    $(error Distribution $(DISTRIBUTION) not supported by builder-github plugin)
endif

# vim: ft=make
