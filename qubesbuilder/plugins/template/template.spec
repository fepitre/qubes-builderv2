#
# This SPEC is for bulding RPM package that contain complete Qubes Template files.
# This includes the VM's root image, patched with all qubes rpms, etc.
#

%{!?template_name: %global template_name %{getenv:TEMPLATE_NAME}}
%{!?version: %global version %(cat version)}
%{!?rel: %global rel %(cat build_timestamp_%{template_name} || echo unavailable)}

%define dest_dir /var/lib/qubes/vm-templates/%{template_name}
%define _binaries_in_noarch_packages_terminate_build 0

Name:           qubes-template-%{template_name}
Version:	    %{version}
Release:	    %{rel}
Summary:	    Qubes OS template for %{template_name}
License:	    GPLv3+
URL:		    http://www.qubes-os.org

Source0:	    root.img
Source1:        appmenus
Source2:        template.conf

Requires:	    xdg-utils
Requires(post):	tar
BuildArch:      noarch
Provides:	    qubes-template
Obsoletes:      %{name} > %{version}-%{release}


%description
%{summary}.


%build
rm -f root.img.part.*
tar --sparse --dereference -cf - %{_sourcedir}/qubeized_images/%{template_name}/root.img | split -d -b 1G - root.img.part.

if [ "0$DISCARD_PREPARED_IMAGE" -eq 1 ]; then
    rm -f root.img
fi


%install
rm -rf $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT/%{dest_dir}

for i in %{_builddir}/root.img.part.*; do
    mv $i $RPM_BUILD_ROOT/%{dest_dir}/
done

touch $RPM_BUILD_ROOT/%{dest_dir}/root.img # we will create the real file in %post
touch $RPM_BUILD_ROOT/%{dest_dir}/private.img # we will create the real file in %post
touch $RPM_BUILD_ROOT/%{dest_dir}/volatile.img # we will create the real file in %post
touch $RPM_BUILD_ROOT/%{dest_dir}/clean-volatile.img.tar # we will create the real file in %post

mkdir -p $RPM_BUILD_ROOT/%{dest_dir}/apps.templates
mkdir -p $RPM_BUILD_ROOT/%{dest_dir}/apps.tempicons
mkdir -p $RPM_BUILD_ROOT/%{dest_dir}/apps
cp %{SOURCE1}/whitelisted-appmenus.list %{SOURCE1}/vm-whitelisted-appmenus.list $RPM_BUILD_ROOT/%{dest_dir}/
cp %{SOURCE1}/netvm-whitelisted-appmenus.list $RPM_BUILD_ROOT/%{dest_dir}/
cp %{SOURCE2} $RPM_BUILD_ROOT/%{dest_dir}/


%pre
export XDG_DATA_DIRS=/usr/share/
if [ "$1" -gt 1 ] ; then
    # upgrading already installed template...
    # avoid removing innocent files if *.desktop doesn't mach anything
    # https://bugs.freedesktop.org/105635
    if ls %{dest_dir}/apps/*.directory %{dest_dir}/apps/*.desktop >/dev/null 2>&1; then
        echo "--> Removing previous menu shortcuts..."
        xdg-desktop-menu uninstall --mode system %{dest_dir}/apps/*.directory %{dest_dir}/apps/*.desktop
    fi
fi


%post
if command -v qvm-template-postprocess >/dev/null 2>&1; then
    qvm-template-postprocess --really post-install %{template_name} %{dest_dir}
    exit $?
fi

echo "--> Processing the root.img... (this might take a while)"
rm -f %{dest_dir}/root.img
cat %{dest_dir}/root.img.part.* | tar --sparse -xf - -C %{dest_dir}
rm -f %{dest_dir}/root.img.part.*
chown root.qubes %{dest_dir}/root.img
chmod 0660 %{dest_dir}/root.img

echo "--> Processing the volatile.img..."
/usr/lib/qubes/prepare-volatile-img.sh %{dest_dir}/volatile.img $[ `stat -c '%s' %{dest_dir}/root.img` / 1024 / 1024 ] || exit 1
chown root.qubes %{dest_dir}/volatile.img
chmod 0660 %{dest_dir}/volatile.img
tar --sparse -cf %{dest_dir}/clean-volatile.img.tar -C %{dest_dir} volatile.img
chown root.qubes %{dest_dir}/clean-volatile.img.tar
chmod 0660 %{dest_dir}/clean-volatile.img.tar

if [ "$1" = 1 ] ; then
    # installing for the first time
    echo "--> Creating private.img..."
    truncate -s 2G %{dest_dir}/private.img
    mkfs.ext4 -m 0 -q -F %{dest_dir}/private.img
    chown root.qubes %{dest_dir}/private.img
    chmod 0660 %{dest_dir}/private.img
fi


export XDG_DATA_DIRS=/usr/share/

echo "--> Instaling menu shortcuts..."

local_user=`getent group qubes | cut -d : -f 4 | cut -d , -f 1`
if [ -n "$local_user" ]; then
    call_as_user() {
        su -c "$*" - $local_user
    }
else
    # This will be the case during installation - user will be created in
    # firstboot. There is also a code to fix file permissions, so not a big problem
    call_as_user() {
        $*
    }
fi

if [ "$1" = 1 ] ; then
    # installing for the first time
    call_as_user qvm-add-template --rpm %{template_name}
fi

# If running inside of chroot (means - from anaconda), force offline mode
if [ "`stat -c %d:%i /`" != "`stat -c %d:%i /proc/1/root/.`" ]; then
    qvm-template-commit --offline-mode %{template_name}
    call_as_user /usr/libexec/qubes-appmenus/create-apps-for-appvm.sh \
        %{dest_dir}/apps.templates %{template_name} vm-templates appvm-black
else
    qvm-template-commit %{template_name}
    qvm-prefs --force-root -s %{template_name} netvm none
    qvm-start --no-guid %{template_name}
    call_as_user qvm-sync-appmenus --force-root %{template_name}
    qvm-shutdown --wait %{template_name}
    qvm-prefs --force-root -s %{template_name} netvm default
    # restore default firewall settings, which was reset by setting netvm=none
    rm -f %{dest_dir}/firewall.xml
    chgrp -R qubes %{dest_dir}
    chmod g+rwX -R %{dest_dir}
fi
exit 0


%preun
if [ "$1" = 0 ] ; then
    # no more packages left

    if command -v qvm-template-postprocess >/dev/null 2>&1; then
        qvm-template-postprocess --really pre-remove %{template_name} %{dest_dir}
        exit $?
    fi

    # First remove DispVM template (even if not exists...)
    qvm-remove --force-root -q %{template_name}-dvm

    if ! qvm-remove --force-root -q --just-db %{template_name}; then
        exit 1
    fi

    rm -f %{dest_dir}/root-cow.img
    rm -f %{dest_dir}/root-cow.img.old
    rm -f %{dest_dir}/firewall.xml
    rm -f %{dest_dir}/%{template_name}.conf
    rm -f %{dest_dir}/updates.stat

    # we need to have it here, because rpm -U <template>
    # apparently executes %preun of the old package *after* %post of the new packages...
    echo "--> Removing menu shortcuts..."
    export XDG_DATA_DIRS=/usr/share/
    xdg-desktop-menu uninstall --mode system %{dest_dir}/apps/*.directory %{dest_dir}/apps/*.desktop

    rm -rf %{dest_dir}/apps %{dest_dir}/apps.templates
    rm -rf %{dest_dir}/apps.icons %{dest_dir}/apps.tempicons
fi


%clean
rm -rf $RPM_BUILD_ROOT


%files
%defattr(660,root,qubes,770)
%attr(2770,root,qubes) %dir %{dest_dir}

%ghost %{dest_dir}/root.img
%ghost %{dest_dir}/volatile.img
%ghost %{dest_dir}/private.img

%{dest_dir}/root.img.part.*
%{dest_dir}/clean-volatile.img.tar

%attr (775,root,qubes) %dir %{dest_dir}/apps
%attr (775,root,qubes) %dir %{dest_dir}/apps.templates
%attr (775,root,qubes) %dir %{dest_dir}/apps.tempicons
%attr (664,root,qubes) %{dest_dir}/whitelisted-appmenus.list
%attr (664,root,qubes) %{dest_dir}/vm-whitelisted-appmenus.list
%attr (664,root,qubes) %{dest_dir}/netvm-whitelisted-appmenus.list
%attr (664,root,qubes) %{dest_dir}/template.conf
