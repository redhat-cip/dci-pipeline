#
# Copyright (C) 2021 Red Hat, Inc.
#
# Author: Frederic Lepied <flepied@redhat.com>
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

'''
'''

import logging

from dciqueue import lib

log = logging.getLogger(__name__)

COMMAND = "add-crontab"


def register_command(subparsers):
    parser = subparsers.add_parser(
        COMMAND, help="Install dci-queue crontab"
    )
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument("file", help="crontab filename to edit")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

    LINE = lib.CRONTAB_LINE_FMT % args.pool

    with open(args.file) as f:
        lines = f.readlines()

    for line in lines:
        line = line.strip("\n")
        if line == LINE:
            return 0

    with open(args.file, "a") as f:
        print(LINE, file=f)

    return 0

# add_crontab_cmd.py ends here
