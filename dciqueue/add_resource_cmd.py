# -*- coding: utf-8 -*-
#
# Copyright (C) 2020 Red Hat, Inc
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations

'''
'''

import logging
import os

log = logging.getLogger(__name__)

COMMAND = 'add-resource'


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help='Create a new resource in a pool')
    parser.add_argument('pool', help='Name of the pool')
    parser.add_argument('name', help='Name of the resource')
    return COMMAND


def execute_command(args):
    f = os.path.join(args.top_dir, 'pool', args.pool, args.name)
    log.debug('Creating %s' % f)
    if not os.path.exists(f):
        open(f, 'w').close()
        os.symlink(f, os.path.join(args.top_dir, 'available', args.pool, args.name))
    return 0

# add_resource_cmd.py ends here
