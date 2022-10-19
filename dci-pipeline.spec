%if 0%{?rhel} && 0%{?rhel} < 8
%global with_python2 1
%global python_sitelib %{python2_sitelib}
%else
%global with_python3 1
%global python_sitelib %{python3_sitelib}
%endif

Name:           dci-pipeline
# to keep in sync with setup.py
Version:        0.0.9
Release:        1.VERS%{?dist}
Summary:        CI pipeline management for DCI jobs
License:        ASL 2.0
URL:            https://github.com/redhat-cip/%{name}
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       jq

%if 0%{?with_python2}
BuildRequires:  python2-devel
BuildRequires:  python2-setuptools
Requires:       PyYAML
Requires:       python2-dciclient >= 2.3.0
Requires:       python2-ansible-runner
Requires:       python-prettytable
Requires:       python2-junit_xml
%endif

%if 0%{?with_python3}
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       python3-PyYAML
Requires:       python3-dciclient >= 2.3.0
Requires:       python3-ansible-runner
Requires:       python3-junit_xml
%endif

BuildRequires:  systemd
%{?systemd_requires}
Requires(pre):  shadow-utils
Requires:       ansible
Requires:       dci-ansible >= 0.3.0
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
install -d -m 755 %{buildroot}%{_datadir}/%{name}/
for tool in extract-dependencies loop_until_failure loop_until_success send-feedback test-runner; do
    install -m 755 tools/$tool %{buildroot}%{_datadir}/%{name}/$tool
done
install -m 755 tools/dci-pipeline-schedule %{buildroot}%{_bindir}/dci-pipeline-schedule
install -m 755 tools/dci-pipeline-check %{buildroot}%{_bindir}/dci-pipeline-check
install -p -D -m 644 dciqueue/dci-queue.bash_completion %{buildroot}%{_sysconfdir}/bash_completion.d/dci-queue
install -d -m 700 %{buildroot}/var/lib/%{name}
install -d -m 700 %{buildroot}/var/lib/dci-queue
install -p -D -m 440 %{name}.sudo %{buildroot}%{_sysconfdir}/sudoers.d/%{name}
cat > %{buildroot}%{_sysconfdir}/%{name}/pipeline.yml <<EOF
---
EOF

%pre
getent group %{name} >/dev/null || groupadd -r %{name}
getent group dci-queue >/dev/null || groupadd -r dci-queue
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
%{_bindir}/dci-pipeline
%{_bindir}/dci-pipeline-schedule
%{_bindir}/dci-pipeline-check
%{_bindir}/dci-agent-ctl
%{_bindir}/dci-queue
%{_bindir}/dci-rebuild-pipeline
%{_bindir}/dci-settings2pipeline
%{_bindir}/dci-diff-pipeline
%attr(770, %{name}, %{name}) /var/lib/%{name}
%attr(2770, dci-queue, dci-queue) /var/lib/dci-queue
%config(noreplace) %{_sysconfdir}/sysconfig/%{name}
%config(noreplace) %{_sysconfdir}/%{name}/pipeline.yml
%config(noreplace) %{_sysconfdir}/bash_completion.d/dci-queue
%{_unitdir}/dci-pipeline.service
%{_unitdir}/dci-pipeline.timer
%{_sysconfdir}/sudoers.d/%{name}
%{_datadir}/%{name}/extract-dependencies
%{_datadir}/%{name}/loop_until_failure
%{_datadir}/%{name}/loop_until_success
%{_datadir}/%{name}/send-feedback
%{_datadir}/%{name}/test-runner

%changelog
* Wed Oct 19 2022 Frederic Lepied <flepied@redhat.com> - 0.0.9-1
- dci-queue is using /var/lib/dci-queue by default

* Wed Oct 12 2022 Frederic Lepied <flepied@redhat.com> - 0.0.8-1
- add dci-pipeline-schedule and dci-pipeline-check
- add jq as a required package

* Thu Sep 15 2022 Frederic Lepied <flepied@redhat.com> - 0.0.7-1
- depends on dci-ansible >= 0.3.0 to have the filter_plugins available

* Thu Mar 24 2022 Frederic Lepied <flepied@redhat.com> - 0.0.6-1
- make use of dci-vault-client

* Mon Dec 13 2021 Frederic Lepied <flepied@redhat.com> 12 2021 - 0.0.5-1
- add dci-settings2pipeline

* Thu Dec  2 2021 Frederic Lepied <flepied@redhat.com> - 0.0.4-1
- add dci-agent-ctl

* Fri May  7 2021 Frederic Lepied <flepied@redhat.com> - 0.0.3-4
- requires junit-xml

* Mon Jan 12 2021 Yassine Lamgarchal <ylamgarc@redhat.com> - 0.0.3-3
- add dci-diff-pipeline

* Mon Jan 11 2021 Yassine Lamgarchal <ylamgarc@redhat.com> - 0.0.3-2
- add dci-rebuild-pipeline

* Fri Sep 25 2020 Frederic Lepied <flepied@redhat.com> - 0.0.3-1
- provide a bash completion file

* Thu Sep 10 2020 Frederic Lepied <flepied@redhat.com> - 0.0.2-1
- add dci-queue files

* Fri Aug 21 2020 Frederic Lepied <flepied@redhat.com> - 0.0.1-2
- add /var/lib/dci-pipeline directory

* Tue Aug 11 2020 Jorge A Gallegos <jgallego@redhat.com> - 0.0.1-1
- Initial build
