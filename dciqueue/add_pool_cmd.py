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

from dciqueue import lib

log = logging.getLogger(__name__)

COMMAND = 'add-pool'


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help='Create a pool of resources')
    parser.add_argument('pool', help='Name of the pool')
    return COMMAND


def execute_command(args):
    for key in ('pool', 'queue', 'available'):
        d = os.path.join(args.top_dir, key, args.pool)
        log.debug('Creating %s %s' % (key, d))
        if not os.path.exists(d):
            os.makedirs(d)

    seq = lib.Seq(args)
    if not seq.exists():
        log.debug('Creating seq file %s' % seq.seqfile)
        seq.lock()
        seq.set(1, 1)
        seq.unlock()

    return 0

# add_pool_cmd.py ends here
