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
import sys

log = logging.getLogger(__name__)

COMMAND = 'schedule'


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help='Schedule a command on a pool')
    parser.add_argument('pool', help='Name of the pool')
    parser.add_argument('cmd', nargs='*')
    return COMMAND


def execute_command(args):
    cmd = ' '.join(args.cmd)
    if '@RESOURCE' not in cmd:
        sys.stderr.write('no @RESOURCE in command: %s\n' % cmd)
        return 1
        
    seqfile = os.path.join(args.top_dir, 'queue', args.pool, '.seq')
    with open(seqfile) as f:
        seq = int(f.read(-1))
    seq += 1
    with open(seqfile, 'w') as f:
        f.write(str(seq))
    log.debug('Updating seq file %s to %d' % (seqfile, seq))

    queuefile = os.path.join(args.top_dir, 'queue', args.pool, str(seq))
    with open(queuefile, 'w') as f:
        f.write(cmd)

    return 0

# schedule_cmd.py ends here
