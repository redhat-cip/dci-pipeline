#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2022 Red Hat, Inc
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


def get_umask():
    mask = None
    try:
        with open("/proc/self/status") as fd:
            for line in fd:
                if line.startswith("Umask:"):
                    mask = int(line[6:].strip(), 8)
                    break
    except FileNotFoundError:
        pass
    except ValueError:
        pass
    if mask is None:
        import subprocess

        mask = int(
            subprocess.check_output("umask", shell=True).decode("utf-8").strip(), 8
        )
    return mask


# set umask to be sure files are user and group writable
def set_umask():
    current_umask = get_umask()
    log.debug("current umask %04o" % current_umask)
    # keep the other part from current umask
    new_umask = 0o020 | (current_umask & 0o007)
    # compute perm without the other part
    current_perms = (0o777 - current_umask) & 0o770
    target_perms = (0o777 - new_umask) & 0o770
    log.debug("current_perms=%04o target_perms=%04o" % (current_perms, target_perms))
    if (current_perms & target_perms) == target_perms:
        log.info("Keeping current umask %04o" % current_umask)
    else:
        log.info("Setting umask %04o" % (new_umask))
        os.umask(new_umask)


def get_default_top_dir():
    top_dir = os.getenv("DCI_QUEUE_DIR", "/var/lib/dci-queue")
    if os.path.exists(top_dir):
        if os.access(top_dir, os.W_OK):
            return top_dir
    elif os.access(os.path.basename(top_dir), os.W_OK):
        return top_dir
    return os.path.expanduser("~/.dci-queue")


def main(cmdargs=sys.argv):
    parser = argparse.ArgumentParser(
        prog=os.path.basename(cmdargs[0]),
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    default_log_level = os.getenv("DCI_QUEUE_LOG_LEVEL", "INFO")
    parser.add_argument(
        "-l",
        "--log-level",
        help="logging level",
        default=default_log_level,
        choices=("DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
    )
    default_top_dir = get_default_top_dir()
    parser.add_argument(
        "-t",
        "--top-dir",
        help="Top directory to store data",
        default=default_top_dir,
    )
    default_console = os.getenv("DCI_QUEUE_CONSOLE_OUTPUT") is not None
    parser.add_argument(
        "-c",
        "--console-output",
        action="store_true",
        help="Output logs to the console",
        default=default_console,
    )
    parser.add_argument(
        "-p",
        "--podman",
        action="store_true",
        help="Called from inside a container",
        default=False,
    )

    subparsers = parser.add_subparsers(
        title="Subcommands", description="valid subcommands", dest="command"
    )

    topdir = os.path.dirname(__file__)

    commands = {}
    for _, name, _ in pkgutil.iter_modules([topdir]):
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

    try:
        if not os.path.exists(args.top_dir):
            try:
                os.makedirs(args.top_dir)
            except PermissionError:
                sys.stderr.write(
                    "Unable to create top dir %s. Aborting.\n" % args.top_dir
                )
                return 1

        if args.console_output:
            logging.basicConfig(
                level=getattr(logging, args.log_level.upper()),
                format=LOG_FORMAT,
            )
        else:
            logging.basicConfig(
                level=getattr(logging, args.log_level.upper()),
                format=LOG_FORMAT,
                filename=os.path.join(args.top_dir, "dci-queue.log"),
            )

        set_umask()

        log.debug("Launching %s" % args.command)
        return commands[args.command](args)
    except Exception as excp:
        sys.stderr.write("Unable to run %s: %s\n" % (args.command, excp))
        log.exception("Unable to run %s" % args.command)
        return 1


if __name__ == "__main__":
    sys.exit(main())

# main.py ends here
