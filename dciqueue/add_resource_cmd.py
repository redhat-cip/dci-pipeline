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

import logging
import os

from dciqueue import lib

log = logging.getLogger(__name__)

COMMAND = "add-resource"


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help="Create a new resource in a pool")
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument("name", help="Name of the resource")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

    f = os.path.join(args.top_dir, "pool", args.pool, args.name)
    if not os.path.exists(f):
        log.debug("Creating %s" % f)
        open(f, "w").close()
    link = os.path.join(args.top_dir, "available", args.pool, args.name)
    if not os.path.exists(link):
        log.debug("Creating %s" % link)
        os.symlink(f, link)
    return 0


# add_resource_cmd.py ends here
