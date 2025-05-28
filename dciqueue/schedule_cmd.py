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
import time

from dciqueue import lib, run_cmd

if sys.version_info[0] == 2:
    FileNotFoundError = IOError

log = logging.getLogger(__name__)

COMMAND = "schedule"


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help="Schedule a command on a pool")
    parser.add_argument(
        "-b",
        "--block",
        help="Block until the command is finished and exit with the return code",
        action="store_true",
    )
    parser.add_argument(
        "-C",
        "--command-output",
        action="store_true",
        help="Command output to the console",
    )
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force the command to be scheduled even if it's duplicated",
    )
    parser.add_argument(
        "-r",
        "--remove-resource",
        action="store_true",
        help="Remove the resource once the job starts",
    )
    parser.add_argument(
        "-p",
        "--priority",
        help="priority level",
        type=int,
        default=0,
    )
    # add -e <pool> option to store multiple pools in the same command
    parser.add_argument("-e", "--extra-pool", action="append", default=[])
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument("cmd", nargs="*")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args.top_dir, args.pool):
        return 1

    for c in args.cmd:
        if "@RESOURCE" in c:
            break
    else:
        sys.stderr.write("no @RESOURCE in command: %s\n" % " ".join(args.cmd))
        return 1

    seq_obj = lib.Seq(args)
    seq_obj.lock()
    first, idx = seq_obj.get()

    found = False
    if not args.force:
        for cmdfile in [
            p
            for p in os.listdir(os.path.join(args.top_dir, "queue", args.pool))
            if p not in (".seq", ".seq.lck")
        ]:
            try:
                with open(
                    os.path.join(args.top_dir, "queue", args.pool, cmdfile), "r"
                ) as f:
                    data = json.load(f)
                if data["cmd"] == args.cmd and data["wd"] == os.getcwd():
                    found = True
                    break
            except FileNotFoundError:
                continue

    if found:
        log.info("Not scheduling a duplicated command")
    else:
        queuefile = os.path.join(args.top_dir, "queue", args.pool, str(idx))
        cwd = os.getcwd()
        # validate extra pools exist
        for pool in args.extra_pool:
            if not lib.check_pool(args.top_dir, pool):
                log.error("Pool %s does not exist" % pool)
                seq_obj.unlock()
                return 1
        with open(queuefile, "w") as f:
            json.dump(
                {
                    "cmd": args.cmd,
                    "wd": cwd,
                    "remove": args.remove_resource,
                    "priority": args.priority,
                    "extra_pools": args.extra_pool,
                },
                f,
            )
        log.info("Command %s (wd: %s) queued as %s" % (args.cmd, cwd, queuefile))
        seq_obj.set(first, idx + 1)

    seq_obj.unlock()

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
