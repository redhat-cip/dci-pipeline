%if 0%{?rhel} && 0%{?rhel} < 8
%global with_python2 1
%global python_sitelib %{python2_sitelib}
%else
%global with_python3 1
%global python_sitelib %{python3_sitelib}
%endif

Name:           dci-pipeline
# to keep in sync with setup.py and Dockerfile
Version:        0.9.0
Release:        1.VERS%{?dist}
Summary:        CI pipeline management for DCI jobs
License:        ASL 2.0
URL:            https://github.com/redhat-cip/%{name}
Source0:        %{name}-%{version}.tar.gz
BuildArch:      noarch

Requires:       jq
Requires:       dci-queue = %{version}-%{release}

%if 0%{?with_python2}
BuildRequires:  python2-devel
BuildRequires:  python2-setuptools
Requires:       PyYAML
Requires:       python2-dciclient >= 3.1.0
Requires:       python2-ansible-runner
Requires:       python-prettytable
Requires:       python2-libselinux
%endif

%if 0%{?with_python3}
BuildRequires:  python3-devel
BuildRequires:  python3-setuptools
Requires:       python3-PyYAML
Requires:       python3-dciclient >= 3.1.0
Requires:       python3-ansible-runner
Requires:       python3-libselinux
%endif

BuildRequires:  systemd
%{?systemd_requires}
Requires(pre):  shadow-utils
Requires:       ansible
Requires:       dci-ansible >= 0.8.0
Requires:       /usr/bin/sudo

%description
CI pipeline management for DCI jobs

%package podman
Summary:        dci-pipeline podman flavour
Requires:       podman
Requires:       dci-queue = %{version}-%{release}

%description podman
CI pipeline management for DCI jobs (via podman)

%package -n dci-queue
Summary:        dci-queue utility
Requires:       cronie

%description -n dci-queue
Queue management for dci-pipeline

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
for tool in alert dci-pipeline-helper extract-dependencies get-config-entry loop_until_failure loop_until_success send_status send_comment test-runner yaml2json; do
    install -m 755 tools/$tool %{buildroot}%{_datadir}/%{name}/$tool
    install -m 755 tools/$tool %{buildroot}%{_datadir}/%{name}/$tool-podman
done
install -m 644 tools/common %{buildroot}%{_datadir}/%{name}/common
install -m 644 tools/common %{buildroot}%{_datadir}/%{name}/common-podman
install -m 755 tools/dci-pipeline-schedule %{buildroot}%{_bindir}/dci-pipeline-schedule
install -m 755 tools/dci-pipeline-schedule %{buildroot}%{_bindir}/dci-pipeline-schedule-podman
install -m 755 tools/dci-pipeline-check %{buildroot}%{_bindir}/dci-pipeline-check
install -m 755 tools/dci-pipeline-check %{buildroot}%{_bindir}/dci-pipeline-check-podman
install -p -D -m 644 dciqueue/dci-queue.bash_completion %{buildroot}%{_sysconfdir}/bash_completion.d/dci-queue
install -d -m 700 %{buildroot}/var/lib/%{name}
install -d -m 700 %{buildroot}/var/lib/dci-queue
install -p -D -m 440 %{name}.sudo %{buildroot}%{_sysconfdir}/sudoers.d/%{name}

for cmd in dci-create-component dci-diff-pipeline dci-find-latest-component dci-openshift-agent-ctl dci-openshift-app-agent-ctl dci-pipeline dci-queue dci-rebuild-pipeline dci-rhel-latest-kernel-version dci-vault-client dci-vault dcictl; do
    install -v -m 755 container/$cmd-podman %{buildroot}%{_bindir}/
done

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

%pre -n dci-queue
getent group dci-queue >/dev/null || groupadd -r dci-queue
exit 0

%files
%license LICENSE
%doc README.md
%if 0%{?with_python2}
%{python2_sitelib}/*
%else
%{python3_sitelib}/*
%endif
%{_bindir}/dci-pipeline
%{_bindir}/dci-auto-launch
%{_bindir}/dci-pipeline-schedule
%{_bindir}/dci-pipeline-check
%{_bindir}/dci-agent-ctl
%{_bindir}/dci-rebuild-pipeline
%{_bindir}/dci-settings2pipeline
%{_bindir}/dci-diff-pipeline
%attr(770, %{name}, %{name}) /var/lib/%{name}
%config(noreplace) %{_sysconfdir}/sysconfig/%{name}
%config(noreplace) %{_sysconfdir}/%{name}/pipeline.yml
%config(noreplace) %{_sysconfdir}/bash_completion.d/dci-queue
%{_unitdir}/dci-pipeline.service
%{_unitdir}/dci-pipeline.timer
%{_sysconfdir}/sudoers.d/%{name}
%{_datadir}/%{name}/alert
%{_datadir}/%{name}/common
%{_datadir}/%{name}/dci-pipeline-helper
%{_datadir}/%{name}/extract-dependencies
%{_datadir}/%{name}/get-config-entry
%{_datadir}/%{name}/loop_until_failure
%{_datadir}/%{name}/loop_until_success
%{_datadir}/%{name}/send_status
%{_datadir}/%{name}/send_comment
%{_datadir}/%{name}/test-runner
%{_datadir}/%{name}/yaml2json

%files podman
%{_bindir}/*-podman
%{_datadir}/%{name}/*-podman

%files -n dci-queue
%{_bindir}/dci-queue
%attr(2770, dci-queue, dci-queue) /var/lib/dci-queue

%changelog
* Fri Jul 19 2024 Frederic Lepied <flepied@redhat.com> 0.9.0-1
- require dci-ansible >= 0.8.0 to get the dcijunit plugin

* Mon Feb 12 2024 Frederic Lepied <flepied@redhat.com> 0.8.4-1
- fix ~ expansion in yaml2json

* Fri Feb  9 2024 Frederic Lepied <flepied@redhat.com> 0.8.3-1
- fix detection of dci-openshift-app-agent in schedule and test-runner

* Tue Feb  6 2024 Frederic Lepied <flepied@redhat.com> 0.8.2-1
- fix dci-queue add-crontab for initial content

* Mon Feb  5 2024 Frederic Lepied <flepied@redhat.com> 0.8.1-1
- fix dci-queue package: descriptions and dependencies

* Sat Feb  3 2024 Frederic Lepied <flepied@redhat.com> 0.8.0-1
- add dci-pipeline-helper

* Wed Jan 17 2024 Frederic Lepied <flepied@redhat.com> 0.7.0-1
- replace send-feedback with send_status and send_comment

* Tue Jan  2 2024 Frederic Lepied <flepied@redhat.com> 0.6.1-1
- send-feedback: support gerrit voting needed by dci-openshift-agent

* Wed Dec  6 2023 Frederic Lepied <flepied@redhat.com> 0.6.0-1
- add dci-auto-launch

* Thu Jul 20 2023 Frederic Lepied <flepied@redhat.com> 0.5.0-1
- add the get-config-entry utility

* Tue Jun 27 2023 Tony Garcia <tonyg@redhat.com> 0.4.0-1
- add alert tool

* Fri Apr 28 2023 Frederic Lepied <flepied@redhat.com> 0.3.0-1
- requires dci-ansible >= 0.3.1 and dciclient >= 3.1.0 for the new
  fields of components

* Thu Nov 17 2022 Frederic Lepied <flepied@redhat.com> 0.2.0-1
- add a dci-queue sub-package
- add dci-pipeline-check-podman and dci-pipeline-schedule-podman to
  the podman package

* Thu Nov  3 2022 Frederic Lepied <flepied@redhat.com> 0.1.0-1
- create the podman sub-package
- add a dependency on python-libselinux

* Fri Oct 28 2022 Frederic Lepied <flepied@redhat.com> - 0.0.11-1
- add common lib

* Thu Oct 27 2022 Frederic Lepied <flepied@redhat.com> - 0.0.10-1
- add yaml2json

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

* Tue Jan 12 2021 Yassine Lamgarchal <ylamgarc@redhat.com> - 0.0.3-3
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
