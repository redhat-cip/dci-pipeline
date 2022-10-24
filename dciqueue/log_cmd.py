# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Red Hat, Inc
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

import logging
import os
import sys
import time

from dciqueue import lib

log = logging.getLogger(__name__)

COMMAND = "log"


def register_command(subparsers):
    parser = subparsers.add_parser(
        COMMAND, help="Display log for a given executed command in a pool"
    )
    parser.add_argument(
        "-f",
        "--follow",
        action="store_true",
        help="Output appended data as the file grows",
    )
    parser.add_argument("-n", "--lines", help="Output the last N lines")
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument("id", help="Id of the run")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

    logfile = os.path.join(args.top_dir, "log", args.pool, args.id)
    if not os.path.exists(logfile):
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, args.id)
        if not os.path.exists(cmdfile):
            sys.stderr.write(("No such file %s\n" % logfile))
            log.error("No such file %s" % logfile)
            return 1
        sys.stderr.write(("Waiting for command %s to start...\n" % args.id))
        while not os.path.exists(logfile):
            time.sleep(1)

    if args.follow or args.lines:
        cmd = "tail"
        cmdargs = [cmd]
        if args.follow:
            cmdargs.append("-f")
        if args.lines:
            cmdargs.append("-n")
            cmdargs.append(args.lines)
    else:
        cmd = "less"
        cmdargs = [cmd]
    cmdargs.append(logfile)
    log.debug("Executing %s" % " ".join(cmdargs))
    os.execlp(cmd, *cmdargs)
    log.error("Should not go here")
    return 1


# add_resource_cmd.py ends here
