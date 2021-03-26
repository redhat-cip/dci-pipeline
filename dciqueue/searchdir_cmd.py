# -*- coding: utf-8 -*-
#
# Copyright (C) 2021 Red Hat, Inc
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

COMMAND = "searchdir"


def register_command(subparsers):
    parser = subparsers.add_parser(
        COMMAND, help="Search the command scheduled from its working directory on a pool of resources"
    )
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument("dir", help="Directory to search")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

    first, next = lib.get_seq(args)

    for idx in range(first, next):
        p = os.path.join(args.top_dir, "queue", args.pool, str(idx))
        if not os.path.exists(p):
            p = os.path.join(args.top_dir, "queue", args.pool, str(idx) + EXT)
            if not os.path.exists(p):
                p = None
        if p:
            with open(p) as f:
                data = json.load(f)
                if data["wd"] == args.dir:
                    print(idx)
                    return 0
    return 1


# searchdir_cmd.py ends here
