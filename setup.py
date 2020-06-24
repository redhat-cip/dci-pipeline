#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the 'License'); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import os
import setuptools

root_dir = os.path.dirname(os.path.abspath(__file__))
readme = open(os.path.join(root_dir, 'README.md')).read()

setuptools.setup(
    name='dcipipeline',
    version='0.0.1',
    packages=setuptools.find_packages(exclude=("tests")),
    author='Distributed CI team',
    author_email='distributed-ci@redhat.com',
    description='DCI Pipeline',
    long_description=readme,
    install_requires=[],
    url='https://github.com/redhat-cip/dci-pipeline',
    license='Apache v2.0',
    classifiers=[
        'Intended Audience :: Developers',
        'Intended Audience :: Information Technology',
        'License :: OSI Approved :: Apache Software License',
        'Operating System :: POSIX :: Linux',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 3',
    ],
    entry_points={
        'console_scripts': ['dci-pipeline=dcipipeline.main:main']
    },
)
