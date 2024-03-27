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
        sed -i -e '/dciclient/d' -e '/dciauth.*/d' requirements.txt
        if [ -r setup.py ]; then
            pip3 install -r requirements.txt .
        else
            pip3 install -r requirements.txt
        fi
    done
fi

## ansible collection source dirs
for d in "$TOPDIR"/ansible-collection-*; do
    cd "$d"
    rm -f ./*.tar.gz
    ansible-galaxy collection build
    # We want to make sure we install the collection we just built
    ansible-galaxy collection install --force ./*.tar.gz
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
# unpin collections provided as local source directories, the previous
# collection install should satisfy the dependency now
for c in $TOPDIR/ansible-collection-c*; do
    # normalize ansible-collection-namespace-name-version -> namespace.name
    name="$(basename $c | sed -e 's/ansible-collection-//' | cut -d '-' -f 1,2 | sed -e 's/-/./')"
    for r in $TOPDIR/dci-openshift-a*/requirements.yml; do
        # get the version string and trim whitespace around it
        cversion="$(grep -A 1 $name $r | tail -1 | xargs)"
        # if there is a version constraint for this collection remove it
        if [[ $cversion = "version:"* ]]; then
            sed -i -e "/$cversion/d" $r
        fi
    done
done

# install whatever other collections are needed
for req in "$TOPDIR"/dci-openshift-*/requirements.yml; do
    cat "$req"
    ansible-galaxy collection install -r "$req"
done

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
