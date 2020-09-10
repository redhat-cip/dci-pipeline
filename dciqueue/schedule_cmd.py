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

"""
"""

import json
import logging
import os
import sys
import time

from dciqueue import lib
from dciqueue import run_cmd

log = logging.getLogger(__name__)

COMMAND = "schedule"


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help="Schedule a command on a pool")
    parser.add_argument(
        "-b",
        "--block",
        help="Block until the command is finished and exit with the return code (default: False)",
        action="store_true",
    )
    parser.add_argument(
        "-C",
        "--command-output",
        action="store_true",
        help="Command output to the console (default False)",
    )
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument("cmd", nargs="*")
    return COMMAND


def execute_command(args):
    for c in args.cmd:
        if "@RESOURCE" in c:
            break
    else:
        sys.stderr.write("no @RESOURCE in command: %s\n" % " ".join(args.cmd))
        return 1

    _, next = lib.inc_seq(args)

    idx = next - 1
    queuefile = os.path.join(args.top_dir, "queue", args.pool, str(idx))
    with open(queuefile, "w") as f:
        json.dump({"cmd": args.cmd, "wd": os.getcwd()}, f)
    log.info("Command queued as %s" % queuefile)

    if args.block:
        log.info("In block mode, running the queue from pool %s" % args.pool)
        while True:
            run_cmd.execute_command(args)
            if os.path.exists(queuefile):
                log.debug("Command not executed. Sleeping 10s.")
                time.sleep(10)
            else:
                log.debug("Command executed")
                return run_cmd.RET_CODE[idx]

    return 0


# schedule_cmd.py ends here
