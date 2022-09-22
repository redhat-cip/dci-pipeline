#!/bin/bash
#
# Copyright (C) 2022 Red Hat, Inc.
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

# This script is called from Dockerfile and zuul. It expects to have
# all the source directories at the same level.

set -ex

TOPDIR=$(cd $(dirname $0)/../..; pwd)

## python deps and source dirs for dci-ansible, dci-pipeline, dciauth and dciclient

# only in Dockerfile mode
if [ -w /usr/share ]; then
    for f in "$TOPDIR"/*dci-[pa]*/requirements.txt "$TOPDIR"/*dci[ac]*/requirements.txt; do
        cd $(dirname $f)
        # remove python libraries provided as local source directories
        sed -i -e '/dciclient/d'  -e '/dciauth.*/d' requirements.txt
        if [ -r setup.py ]; then
            pip install -r requirements.txt .
        else
            pip install -r requirements.txt
        fi
    done
fi

## ansible collection source dirs
for d in "$TOPDIR"/ansible-collection-*; do
    cd "$d"
    rm -f ./*.tar.gz
    ansible-galaxy collection build
    ansible-galaxy collection install ./*.tar.gz
done

## ansible roles source dirs
for d in "$TOPDIR"/ansible-role-*; do
    cd "$d"
    if [ -n "$ANSIBLE_DIR" ]; then
        make install DATADIR="$ANSIBLE_DIR"
    else
        make install
    fi
done

## ansible collection deps

# remove collections provided as local source directories
sed -i -e '/community.kubernetes/d' -e '/community.libvirt/d' -e '/containers.podman/d' "$TOPDIR"/dci-openshift-*/requirements.yml

cat "$TOPDIR"/dci-openshift*/requirements.yml

ansible-galaxy collection install -r "$TOPDIR"/dci-openshift-agent*/requirements.yml
ansible-galaxy list

## agents

# only install in Dockerfile mode
if [ -w /usr/share ]; then
    cd "$TOPDIR"/dci-openshift-agent*
    make install

    cd "$TOPDIR"/dci-openshift-app-agent*
    make install
fi

# install-from-source.sh ends here
