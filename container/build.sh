#!/bin/bash
#
# Copyright (C) 2022-2023 Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

set -ex

if [ $# = 0 ]; then
    TAG=dci-pipeline
else
    TAG="$1"
fi

cd $(dirname $(cd $(dirname $0); pwd))

if [ $(id -u) -eq 0 ]; then
    wget -O /etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-beta  https://www.redhat.com/security/data/897da07a.txt
    chcon --reference /etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-release /etc/pki/rpm-gpg/RPM-GPG-KEY-redhat-beta
fi

for dir in . ../python-dciclient ../python-dciauth; do
    cd $dir
    rm -rf dist
    python3 setup.py sdist
    cd -
done

for dir in dci-ansible \
    dci-openshift-agent \
    dci-openshift-app-agent \
    ansible-collection-community-kubernetes \
    ansible-collection-community-general \
    ansible-collection-community-libvirt \
    ansible-collection-containers-podman \
    ansible-role-dci-podman \
    ansible-role-dci-sync-registry \
    ; do
    cd  ../$dir
    VERS=$(sed -n -e "s/Version:\s*\([^ ]*\)\s*/\1/p" $dir.spec)
    git archive "--output=../dci-pipeline/dist/$dir-$VERS.tar.gz" "--prefix=$dir-$VERS/" --format=tar HEAD
    cd -
done

cp ../python-dciclient/dist/* dist/
cp ../python-dciauth/dist/* dist/

podman build -t "$TAG" .

# build.sh ends here
