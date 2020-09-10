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

'''
'''

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
REGISTER_ENTRY_POINT = 'register_command' # register subparser
EXECUTE_ENTRY_POINT = 'execute_command'   # execute sub-command


def main(cmdargs=sys.argv):
    parser = argparse.ArgumentParser(prog=os.path.basename(cmdargs[0]))
    default_log_level = os.getenv('QUEUE_LOG_LEVEL', 'WARNING')
    parser.add_argument('--log-level',
                        help='logging level (default %s)' % default_log_level,
                        default=default_log_level)
    default_top_dir = os.getenv('QUEUE_DIR', os.path.expanduser('~/.queue'))
    parser.add_argument(
        '--top-dir',
        help='Top directory to store data (default %s)' % default_top_dir,
        default=default_top_dir
    )

    subparsers = parser.add_subparsers(
        title='Subcommands', description='valid subcommands', dest="command"
    )

    topdir = os.path.dirname(__file__)

    commands = {}
    for (_, name, _) in pkgutil.iter_modules([topdir]):
        if name.endswith('_cmd'):
            imported_module = importlib.import_module('dciqueue.' + name)
            if (not REGISTER_ENTRY_POINT in dir(imported_module)
                and not EXECUTE_ENTRY_POINT in dir(imported_module)):
                sys.stderr.write('Invalid command file %s\n' % name)
                continue
            cmd = getattr(imported_module, REGISTER_ENTRY_POINT)(subparsers)
            commands[cmd] = getattr(imported_module, EXECUTE_ENTRY_POINT)

    args = parser.parse_args(cmdargs[1:])

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    if not args.command:
        parser.print_usage()
        return 1

    log.debug('Launching %s' % args.command)
    return commands[args.command](args)


if __name__ == '__main__':
    sys.exit(main())        

# main.py ends here
