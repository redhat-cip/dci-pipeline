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

""" """

import datetime
import errno
import json
import logging
import os
import subprocess
import sys

from dciqueue import lib

log = logging.getLogger(__name__)

COMMAND = "remove-resource"


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help="Remove a resource from a pool")
    parser.add_argument(
        "-f",
        "--force",
        action="store_true",
        help="Force the removal of the resource from the pool",
    )
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument("name", help="Name of the resource")
    parser.add_argument("reason", help="Reason of the removal")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

    # if we are trying to remove a resource that does not exist, but not forcing the
    # removal of the resource, then exit
    path = os.path.join(args.top_dir, "pool", args.pool, args.name)
    if not (os.path.exists(path) or args.force):
        msg = "Trying to remove resource %s that does not exist." % (args.name,)
        sys.stderr.write(msg)
        return 1

    # this step is common when forcing and not forcing the removal
    for key in ("available", "pool"):
        path = os.path.join(args.top_dir, key, args.pool, args.name)
        if os.path.exists(path) or os.path.islink(path):
            log.debug("Removing %s (%s)" % (path, args.reason))
            os.unlink(path)

    dir = os.path.join(args.top_dir, "reason", args.pool)
    try:
        os.makedirs(dir)
    except OSError as e:
        if e.errno == errno.EEXIST:
            pass
        else:
            raise

    path = os.path.join(args.top_dir, "reason", args.pool, args.name)
    if args.force:
        # files under available and pool directories have already been removed
        # if present
        # now, just check if the resource is already blocked, to remove it from
        # the blocked resources (reason directory), then finish the execution
        if os.path.exists(path):
            os.unlink(path)
        return 0

    # if we're not forcing the removal of the resource, just move it to the
    # removed resources including the reason of the removal if provided
    # Use tmux session name as a prefix if any
    prefix = ""
    if os.environ.get("TMUX"):
        prefix = subprocess.check_output(
            "tmux display-message -p '#S: '||:",
            stderr=subprocess.DEVNULL,
            shell=True,
            universal_newlines=True,
        ).strip("\n")

    with open(path, "w") as f:
        json.dump(
            {
                "reason": prefix + args.reason,
                "pool": args.pool,
                "resource": args.name,
                "date": str(datetime.datetime.now()),
            },
            f,
        )

    return 0


# remove_resource_cmd.py ends here
