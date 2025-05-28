# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2025 Red Hat, Inc
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

""" """

import json
import logging
import os
import sys

from dciqueue import lib
from dciqueue.run_cmd import EXT

log = logging.getLogger(__name__)

COMMAND = "list"


def register_command(subparsers):
    parser = subparsers.add_parser(
        COMMAND, help="List the commands scheduled on a pool of resources"
    )
    parser.add_argument("pool", help="Name of the pool", nargs="?", default=None)
    return COMMAND


def execute_command(args):
    if args.pool is None:
        d = os.path.join(args.top_dir, "pool")
        if os.path.exists(d):
            p = os.listdir(d)
            if len(p) == 0:
                print("No pool was found on the host.")
            else:
                print("The following pools were found:")
                for pool in p:
                    print("  " + pool)
                print(
                    "Run the command below for the list of commands scheduled on your target pool:"
                )
                print("  " + sys.argv[0] + " list <pool>")
        return 0

    if not lib.check_pool(args.top_dir, args.pool):
        return 1

    first, next = lib.get_seq(args)

    print(
        "Resources on the %s pool: %s"
        % (
            args.pool,
            " ".join(os.listdir(os.path.join(args.top_dir, "pool", args.pool))),
        )
    )

    print(
        "Available resources on the %s pool: %s"
        % (
            args.pool,
            " ".join(os.listdir(os.path.join(args.top_dir, "available", args.pool))),
        )
    )

    reasondir = os.path.join(args.top_dir, "reason", args.pool)
    if os.path.exists(reasondir):
        reasons = []
        for fname in os.listdir(reasondir):
            reasonfile = os.path.join(reasondir, fname)
            if os.path.exists(reasonfile):
                with open(reasonfile) as f:
                    data = json.load(f)
                    reasons.append(data)
        if reasons != []:
            print("Removed resources on the %s pool:" % args.pool)
            for d in reasons:
                print(" %s: %s [%s]" % (d["resource"], d["reason"], d["date"]))

    print("Executing commands on the %s pool:" % args.pool)
    for path in [
        p
        for p in os.listdir(os.path.join(args.top_dir, "queue", args.pool))
        if p.endswith(EXT)
    ]:
        display_cmd(args, path, EXT)

    print("Queued commands on the %s pool:" % args.pool)
    for fname in sorted(
        range(first, next), key=lambda x: get_pri(args, x), reverse=True
    ):
        display_cmd(args, str(fname))

    return 0


def display_cmd(args, filename, ext=None):
    cmdfile = os.path.join(args.top_dir, "queue", args.pool, filename)
    if os.path.exists(cmdfile):
        with open(cmdfile) as f:
            data = json.load(f)
            if "real_cmd" in data:
                cmd = data["real_cmd"]
            else:
                cmd = data["cmd"]
            print(
                " %s%s%s: %s (wd: %s)%s"
                % (
                    filename[: -len(ext)] if ext else filename,
                    (
                        "(p%d)" % data["priority"]
                        if "priority" in data and data["priority"] > 0
                        else ""
                    ),
                    " [%s]" % data["resource"] if "resource" in data else "",
                    " ".join(cmd),
                    data["wd"],
                    " [REMOVE]" if "remove" in data and data["remove"] else "",
                )
            )


def get_pri(args, filename):
    cmdfile = os.path.join(args.top_dir, "queue", args.pool, str(filename))
    if os.path.exists(cmdfile):
        with open(cmdfile) as f:
            data = json.load(f)
            return data["priority"] if "priority" in data else 0
    return 0


# list_pool_cmd.py ends here
