# -*- coding: utf-8 -*-
#
# Copyright (C) 2022 Red Hat, Inc
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

from dciqueue import run_cmd

if sys.version_info[0] == 2:
    FileNotFoundError = OSError

log = logging.getLogger(__name__)

COMMAND = "clean"


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help="Clean stale commands from a pool")
    parser.add_argument("pool", help="Name of the pool")
    return COMMAND


def execute_command(args):
    """Find EXT files in the queue and check if they are still in use."""
    queue_dir = os.path.join(args.top_dir, "queue", args.pool)
    execfiles = [f for f in os.listdir(queue_dir) if f.endswith(run_cmd.EXT)]

    # Check if the pid is still running
    for execfile in execfiles:
        with open(os.path.join(queue_dir, execfile)) as f:
            data = json.load(f)
            res = data.get("resource")
            pid = data.get("pid")
            if pid and res:
                try:
                    os.kill(pid, 0)
                except ProcessLookupError:
                    log.info(
                        "Stale PID %s found in pool %s under resource %s"
                        % (pid, args.pool, res)
                    )
                    log.info("Deleting stale file %s.%s" % (pid, run_cmd.EXT))
                    path = os.path.join(args.top_dir, "queue", args.pool, execfile)
                    os.unlink(path)
                    free_resource(res, args)

    return 0


def free_resource(res, args):
    path = os.path.join(args.top_dir, "pool", args.pool, res)

    if os.path.exists(path):
        symlink = os.path.join(args.top_dir, "available", args.pool, res)
        log.debug("Creating symlink %s" % symlink)
        os.symlink(path, symlink)


# clean_cmd.py ends here
