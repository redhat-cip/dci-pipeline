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

import json
import logging
import os
import subprocess

from dciqueue import lib

log = logging.getLogger(__name__)

COMMAND = "run"


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help="Run a command from a pool")
    parser.add_argument("pool", help="Name of the pool")
    return COMMAND


def execute_command(args):
    commands = []

    while True:
        res = book_resource(args)

        if res is None:
            log.debug("No available resource anymore in pool %s" % args.pool)
            break

        to_exec, idx = get_command(args)

        if not to_exec:
            log.debug("No command to run in pool %s" % args.pool)
            free_resource(res, args)
            break
        else:
            with open(to_exec) as f:
                data = json.load(f)

                cmd = [c.replace("@RESOURCE", res) for c in data["cmd"]]

                log.debug("Removing %s" % to_exec)
                os.remove(to_exec)

                try:
                    log.info("Running command %s (wd: %s)" % (cmd, data["wd"]))
                    os.chdir(data["wd"])
                    out_fd = open(
                        os.path.join(args.top_dir, "log", args.pool, str(idx)), "w"
                    )
                    proc = subprocess.Popen(cmd, stdout=out_fd, stderr=out_fd)
                    commands.append([res, proc, out_fd, cmd])
                except Exception:
                    log.exception("Unable to execute command")
                    free_resource(res, args)

    for res, proc, fd, cmd in commands:
        if proc:
            proc.wait()
            fd.close()
            log.info("%s returned %d" % (cmd, proc.returncode))
        free_resource(res, args)

    return 0


def book_resource(args):
    available_dir = os.path.join(args.top_dir, "available", args.pool)
    resources = [
        f
        for f in os.listdir(available_dir)
        if os.path.islink(os.path.join(available_dir, f))
    ]

    if len(resources) == 0:
        return None

    for res in resources:
        try:
            os.remove(os.path.join(args.top_dir, "available", args.pool, res))
            return res
        except FileNotFoundError:
            continue
    return None


def free_resource(res, args):
    path = os.path.join(args.top_dir, "pool", args.pool, res)
    os.symlink(path, os.path.join(args.top_dir, "available", args.pool, res))


def get_command(args):
    seq = lib.Seq(args)

    seq.lock()
    first, next = seq.get()

    to_exec = None
    indice = None
    for idx in range(first, next):
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, str(idx))
        try:
            movedfile = cmdfile + ".lck"
            os.rename(cmdfile, movedfile)
            to_exec = movedfile
            indice = idx
            seq.set(idx + 1, next)
            break
        except FileNotFoundError:
            continue

    seq.unlock()
    return to_exec, indice


# run_cmd.py ends here
