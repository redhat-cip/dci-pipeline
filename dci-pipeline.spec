%if 0%{?rhel} && 0%{?rhel} < 8
%global with_python2 1
%global python_sitelib %{python2_sitelib}
%else
%global with_python3 1
%global python_sitelib %{python3_sitelib}
%endif

Name:           dci-pipeline
Version:        0.0.3
Release:        1.VERS%{?dist}
Summary:        CI pipeline management for DCI jobs
License:        ASL 2.0
# TODO: actually mirror on github
URL:            https://github.com/redhat-cip/%{name}
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

%if 0%{?with_python2}
BuildRequires:  python2-devel
BuildRequires:  python2-setuptools
Requires:       PyYAML
Requires:       python2-dciclient
Requires:       python2-ansible-runner
%endif

%if 0%{?with_python3}
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       python3-PyYAML
Requires:       python3-dciclient
Requires:       python3-ansible-runner
%endif

BuildRequires:  systemd
%{?systemd_requires}
Requires(pre):  shadow-utils
Requires:       ansible
Requires:       dci-ansible
Requires:       /usr/bin/sudo

%description
CI pipeline management for DCI jobs

%prep -a -v
%autosetup -n %{name}-%{version}

%build
%if 0%{?with_python2}
%py2_build
%endif
%if 0%{?with_python3}
%py3_build
%endif

%install
%if 0%{?with_python2}
%py2_install
%endif
%if 0%{?with_python3}
%py3_install
%endif

install -p -D -m 644 systemd/%{name}.service %{buildroot}%{_unitdir}/%{name}.service
install -p -D -m 644 systemd/%{name}.timer %{buildroot}%{_unitdir}/%{name}.timer
install -p -D -m 644 sysconfig/%{name} %{buildroot}%{_sysconfdir}/sysconfig/%{name}
install -d -m 755 %{buildroot}%{_sysconfdir}/%{name}
install -d -m 755 %{buildroot}%{_sysconfdir}/bash_completion.d
install -p -D -m 644 dciqueue/dci-queue.bash_completion %{buildroot}%{_sysconfdir}/bash_completion.d/dci-queue
install -d -m 700 %{buildroot}/var/lib/%{name}
install -p -D -m 440 %{name}.sudo %{buildroot}%{_sysconfdir}/sudoers.d/%{name}
cat > %{buildroot}%{_sysconfdir}/%{name}/pipeline.yml <<EOF
---
EOF

%pre
getent group %{name} >/dev/null || groupadd -r %{name}
getent passwd %{name} >/dev/null || \
    useradd -m -g %{name} -d %{_sharedstatedir}/%{name} -s /bin/bash \
            -c "%{summary}" %{name}
exit 0

%post
%systemd_post %{name}.service
%systemd_preun %{name}.timer

%preun
%systemd_preun %{name}.service
%systemd_preun %{name}.timer

%postun
%systemd_postun %{name}.service
%systemd_postun %{name}.timer

%files
%license LICENSE
%doc README.md
%if 0%{?with_python2}
%{python2_sitelib}/*
%else
%{python3_sitelib}/*
%endif
%{_bindir}/%{name}
%{_bindir}/dci-queue
%{_bindir}/dci-rebuild-pipeline
%{_bindir}/dci-diff-pipeline
%attr(770, %{name}, %{name}) /var/lib/%{name}
%config(noreplace) %{_sysconfdir}/sysconfig/%{name}
%config(noreplace) %{_sysconfdir}/%{name}/pipeline.yml
%config(noreplace) %{_sysconfdir}/bash_completion.d/dci-queue
%{_unitdir}/dci-pipeline.service
%{_unitdir}/dci-pipeline.timer
%{_sysconfdir}/sudoers.d/%{name}

%changelog
* Mon Jan 12 2021 Yassine Lamgarchal <ylamgarc@redhat.com> 0.0.3-3.VERS
- add dci-diff-pipeline

* Mon Jan 11 2021 Yassine Lamgarchal <ylamgarc@redhat.com> 0.0.3-2.VERS
- add dci-rebuild-pipeline

* Fri Sep 25 2020 Frederic Lepied <flepied@redhat.com> 0.0.3-1.VERS
- provide a bash completion file

* Thu Sep 10 2020 Frederic Lepied <flepied@redhat.com> - 0.0.2-1
- add dci-queue files

* Fri Aug 21 2020 Frederic Lepied <flepied@redhat.com> - 0.0.1-2
- add /var/lib/dci-pipeline directory

* Tue Aug 11 2020 Jorge A Gallegos <jgallego@redhat.com> - 0.0.1-1
- Initial build
