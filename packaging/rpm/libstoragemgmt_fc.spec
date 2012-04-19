Name:           libstoragemgmt
Version:        0.0.5
Release:        1%{?dist}
Summary:        Storage array management library
Group:          System Environment/Libraries
License:        LGPLv2+
URL:            http://sourceforge.net/projects/libstoragemgmt/ 
Source0:        http://sourceforge.net/projects/libstoragemgmt/files/Alpha/libstoragemgmt-0.0.5.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)

BuildRequires:  boost-devel yajl-devel libxml2-devel tog-pegasus-devel python2-devel pywbem
Requires:       pywbem initscripts 
Requires(post): systemd-units
Requires(preun): systemd-units
Requires(postun): systemd-units

%description
The libStorageMgmt library will provide a vendor agnostic open source storage
application programming interface (API) that will allow management of storage 
arrays.  The library includes a command line interface for interactive use and
scripting (command lsmcli).  The library also has a daemon that is used for
executing plug-ins in a separate process (lsmd).

%package        devel
Summary:        Development files for %{name}
Group:          Development/Libraries
Requires:       %{name}%{?_isa} = %{version}-%{release}

%description    devel
The %{name}-devel package contains libraries and header files for
developing applications that use %{name}.


%prep
%setup -q

%build
%configure --disable-static
make %{?_smp_mflags}


%install
rm -rf %{buildroot}
make install DESTDIR=%{buildroot}
find %{buildroot} -name '*.la' -exec rm -f {} ';'

install -d -m755 %{buildroot}/%{_unitdir}
install -m644 packaging/daemon/libstoragemgmt.service %{buildroot}/%{_unitdir}/libstoragemgmt.service

#tempfiles.d configuration for /var/run
mkdir -p %{buildroot}%{_sysconfdir}/tmpfiles.d
install -m 0644 packaging/daemon/lsm-tmpfiles.conf %{buildroot}%{_sysconfdir}/tmpfiles.d/%{name}.conf

#Need these to exist at install so we can start the daemon
mkdir -p %{buildroot}%{_localstatedir}/run/lsm/ipc

%clean
rm -rf %{buildroot}

%pre
getent group libstoragemgmt >/dev/null || groupadd -r libstoragemgmt
getent passwd libstoragemgmt >/dev/null || \
    useradd -r -g libstoragemgmt -d /var/run/lsm -s /sbin/nologin \
    -c "daemon account for libstoragemgmt" libstoragemgmt

%post
/sbin/ldconfig
if [ $1 -eq 1 ]; then
    /bin/systemctl enable libstoragemgmt.service >/dev/null 2>&1 || :
    /bin/systemctl start libstoragemgmt.service >/dev/null 2>&1 || :
fi

%preun
if [ $1 -eq 0 ]; then
        # On uninstall (not upgrade), disable and stop the units
        /bin/systemctl --no-reload disable libstoragemgmt.service >/dev/null 2>&1 || :
        /bin/systemctl stop libstoragemgmt.service >/dev/null 2>&1 || :
fi

%postun
/sbin/ldconfig
/bin/systemctl daemon-reload >/dev/null 2>&1 || :
if [ $1 -ge 1 ] ; then
        # On upgrade (not uninstall), optionally, restart the daemon
        /bin/systemctl try-restart libstoragemgmt.service >/dev/null 2>&1 || :
fi

%files
%defattr(-,root,root,-)
%doc README COPYING.LIB
%{_mandir}/man1/lsmcli.1*
%{_mandir}/man1/lsmd.1*
%{_libdir}/*.so.*
%{_bindir}/*

#Python library files
%{python_sitelib}/*

%{_unitdir}/*

%dir %attr(0755, libstoragemgmt, libstoragemgmt) %{_localstatedir}/run/lsm/
%dir %attr(0755, libstoragemgmt, libstoragemgmt) %{_localstatedir}/run/lsm/ipc
%config(noreplace) %{_sysconfdir}/tmpfiles.d/%{name}.conf

%files devel
%defattr(-,root,root,-)
%{_includedir}/*
%{_libdir}/*.so


%changelog
* Mon Mar 26 2012 Tony Asleson <tasleson@redhat.com> 0.0.4-1
- Restore from snapshot
- Job identifiers string instead of integer
- Updated license address

* Wed Mar 14 2012 Tony Asleson <tasleson@redhat.com> 0.0.3-1
- Changes to installer, daemon uid, gid, /var/run/lsm/*
- NFS improvements and bug fixes
- Python library clean up (rpmlint errors)

* Sun Mar 11 2012 Tony Asleson <tasleson@redhat.com> 0.0.2-1
- Added NetApp native plugin

* Mon Feb 6 2012 Tony Asleson <tasleson@redhat.com>  0.0.1alpha-1
- Initial version of package