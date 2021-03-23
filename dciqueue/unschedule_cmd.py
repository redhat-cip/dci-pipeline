# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2021 Red Hat, Inc
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

"""
"""

import json
import logging
import os
import signal
import sys

from dciqueue import lib
from dciqueue.run_cmd import EXT

if sys.version_info[0] == 2:
    FileNotFoundError = OSError

log = logging.getLogger(__name__)

COMMAND = "unschedule"


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help="Un-schedule a command from a pool")
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument("id", help="Command id")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

    queuefile = os.path.join(args.top_dir, "queue", args.pool, str(args.id))
    log.info("Un-queuing command %s from %s" % (args.id, args.pool))

    try:
        os.unlink(queuefile)
    except FileNotFoundError:
        queuefile = os.path.join(args.top_dir, "queue", args.pool, str(args.id) + EXT)
        if os.path.exists(queuefile):
            with open(queuefile) as f:
                data = json.load(f)
                if "pid" in data:
                    log.info("Un-queuing command %s from %s by killing %d" % (args.id, args.pool, data["pid"]))
                    os.kill(data["pid"], signal.SIGTERM)
                    try:
                        os.unlink(queuefile)
                    except FileNotFoundError:
                        pass
                else:
                    sys.stderr.write("Unable to stop command %d\n" % args.id)
                    return 1
        else:
            log.info("File not found %s" % queuefile)
    return 0


# unschedule_cmd.py ends here
