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
import subprocess
import sys

from dciqueue import lib

log = logging.getLogger(__name__)

COMMAND = 'run'


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help='Run a command from a pool')
    parser.add_argument('pool', help='Name of the pool')
    return COMMAND


def execute_command(args):
    seq = lib.get_seq(args)

    last = None
    for idx in range(seq, 0, -1):
        cmdfile = os.path.join(args.top_dir, 'queue', args.pool, str(idx))
        if os.path.exists(cmdfile):
            last = cmdfile

    if not last:
        log.debug('No command to run in pool %s' % args.pool)
        return 0

    with open(last) as f:
        cmd = f.read()

    available_dir = os.path.join(args.top_dir, 'available', args.pool)
    resources = [f for f in os.listdir(available_dir) if os.path.islink(os.path.join(available_dir, f))]
    
    if len(resources) == 0:
        log.info('No available resource in pool %s' % args.pool)
        return 0
    
    os.remove(os.path.join(args.top_dir, 'available', args.pool, resources[0]))

    cmd = cmd.replace('@RESOURCE', resources[0])

    log.debug('Removing %s' % last)
    os.remove(last)

    log.debug('Running command %s' % cmd)
    subprocess.call(cmd.split(' '))

    f = os.path.join(args.top_dir, 'pool', args.pool, resources[0])
    os.symlink(f, os.path.join(args.top_dir, 'available', args.pool, resources[0]))

    return 0

# run_cmd.py ends here
