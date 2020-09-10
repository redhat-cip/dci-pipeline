#!/usr/bin/env python
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

import argparse
import importlib
import logging
import os
import pkgutil
import sys

log = logging.getLogger(__name__)

# Sub-command modules need to have the following constraints:
# - be the same directory as dciqueue.main
# - end in _cmd.py
# - have the following entry points
REGISTER_ENTRY_POINT = "register_command"  # register subparser and return command name
EXECUTE_ENTRY_POINT = "execute_command"  # execute sub-command

LOG_FORMAT = "%(asctime)s - %(process)s - %(name)s - %(levelname)s - %(message)s"


def main(cmdargs=sys.argv):
    parser = argparse.ArgumentParser(prog=os.path.basename(cmdargs[0]))
    default_log_level = os.getenv("QUEUE_LOG_LEVEL", "WARNING")
    parser.add_argument(
        "-l",
        "--log-level",
        help="logging level (default %s)" % default_log_level,
        default=default_log_level,
    )
    default_top_dir = os.getenv("QUEUE_DIR", os.path.expanduser("~/.queue"))
    parser.add_argument(
        "-t",
        "--top-dir",
        help="Top directory to store data (default %s)" % default_top_dir,
        default=default_top_dir,
    )
    default_console = os.getenv("QUEUE_CONSOLE_OUTPUT") is not None
    parser.add_argument(
        "-c",
        "--console-output",
        action="store_true",
        help="Output logs to the console (default %s)" % default_console,
        default=default_console,
    )

    subparsers = parser.add_subparsers(
        title="Subcommands", description="valid subcommands", dest="command"
    )

    topdir = os.path.dirname(__file__)

    commands = {}
    for (_, name, _) in pkgutil.iter_modules([topdir]):
        if name.endswith("_cmd"):
            imported_module = importlib.import_module("dciqueue." + name)
            if REGISTER_ENTRY_POINT not in dir(
                imported_module
            ) and EXECUTE_ENTRY_POINT not in dir(imported_module):
                sys.stderr.write("Invalid command file %s\n" % name)
                continue
            cmd = getattr(imported_module, REGISTER_ENTRY_POINT)(subparsers)
            commands[cmd] = getattr(imported_module, EXECUTE_ENTRY_POINT)

    args = parser.parse_args(cmdargs[1:])

    if not args.command:
        parser.print_usage()
        return 1

    if not os.path.exists(args.top_dir):
        os.makedirs(args.top_dir)

    if args.console_output:
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper()),
            format=LOG_FORMAT,
        )
    else:
        logging.basicConfig(
            level=getattr(logging, args.log_level.upper()),
            format=LOG_FORMAT,
            filename=os.path.join(args.top_dir, "queue.log"),
        )

    log.debug("Launching %s" % args.command)
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())

# main.py ends here
