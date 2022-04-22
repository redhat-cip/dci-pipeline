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

"""
"""
import os
import re
import sys
import logging

from dciqueue import lib

log = logging.getLogger(__name__)

COMMAND = "dci-job"


def register_command(subparsers):
    parser = subparsers.add_parser(
        COMMAND,
        help="Display a list of job IDs and its name, for a given executed command in a pool",
    )
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument("id", help="ID of the run")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

    logfile = os.path.join(args.top_dir, "log", args.pool, args.id)
    if not os.path.exists(logfile):
        sys.stderr.write(
            ("No log file found in (pool/id): %s/%s\n" % (args.pool, args.id))
        )
        log.error("No log file found in (pool/id): %s/%s\n" % (args.pool, args.id))
        return 1

    jobs = []
    job_id_regex = re.compile(r"Setting tag job:([\w-]+) on job ([0-9a-f-]+)$")

    with open(logfile, "r") as f:
        lines = f.readlines()

    for line in lines:
        m = job_id_regex.search(line)
        if m:
            jobs.append("%s:%s" % (m.group(1), m.group(2)))

    if jobs:
        sys.stdout.write("\n".join(jobs))
    else:
        sys.stderr.write(
            "No DCI job IDs found in (pool/id): %s/%s\n" % (args.pool, args.id)
        )
        log.error("No DCI job IDs found in (pool/id): %s/%s" % (args.pool, args.id))
        return 1

    return 0


# info_cmd.py ends here
