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

from dciqueue import lib
from dciqueue.run_cmd import EXT

log = logging.getLogger(__name__)

COMMAND = "list"


def register_command(subparsers):
    parser = subparsers.add_parser(
        COMMAND, help="List the commands scheduled on a pool of resources"
    )
    parser.add_argument("pool", help="Name of the pool")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

    first, next = lib.get_seq(args)

    print("Executing commands on the %s pool:" % args.pool)
    for path in [p for p in os.listdir(os.path.join(args.top_dir, "queue", args.pool)) if p.endswith(EXT)]:
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, path)
        if os.path.exists(cmdfile):
            with open(cmdfile) as f:
                data = json.load(f)
                print("%s: %s (wd: %s)" % (path[:-len(EXT)], " ".join(data["cmd"]), data["wd"]))

    print("Queued commands on the %s pool:" % args.pool)
    for idx in range(first, next):
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, str(idx))
        if os.path.exists(cmdfile):
            with open(cmdfile) as f:
                data = json.load(f)
                print("%d: %s (wd: %s)" % (idx, " ".join(data["cmd"]), data["wd"]))

    return 0


# list_pool_cmd.py ends here
