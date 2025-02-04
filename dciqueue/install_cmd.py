#
# Copyright (C) 2021-2022 Red Hat, Inc.
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

""" """

import logging
import os

from dciqueue import add_crontab_cmd, lib

log = logging.getLogger(__name__)

COMMAND = "install"


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help="Install dci-queue")
    parser.add_argument("pool", help="Name of the pool")
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

    if args.podman:
        add_crontab_cmd.execute_command(args)
    else:
        cmd = "env EDITOR='dci-queue add-crontab %s' crontab -e" % args.pool
        log.info("Editing crontab with: '%s'" % cmd)
        os.system(cmd)

    return 0


# install_cmd.py ends here
