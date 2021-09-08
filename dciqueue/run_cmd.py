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

"""
"""

import json
import logging
import os
import subprocess
import sys

from dciqueue import lib

if sys.version_info[0] == 2:
    FileNotFoundError = OSError

log = logging.getLogger(__name__)

COMMAND = "run"

EXT = ".exec"
RET_CODE = {}


def register_command(subparsers):
    parser = subparsers.add_parser(COMMAND, help="Run a command from a pool")
    parser.add_argument("pool", help="Name of the pool")
    parser.add_argument(
        "-C",
        "--command-output",
        action="store_true",
        help="Command output to the console",
    )
    return COMMAND


def execute_command(args):
    if not lib.check_pool(args):
        return 1

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

                data["real_cmd"] = [c.replace("@RESOURCE", res) for c in data["cmd"]]
                data["resource"] = res
                data["jobid"] = idx

                if "remove" in data and data["remove"]:
                    log.info("Removing resource %s" % res)
                    path = os.path.join(args.top_dir, "pool", args.pool, res)
                    if os.path.exists(path):
                        os.unlink(path)

            with open(to_exec, "w") as f:
                json.dump(data, f)

            try:
                log.info("Running command %s (wd: %s)" % (data["cmd"], data["wd"]))
                os.chdir(data["wd"])
                os.environ["DCI_QUEUE_JOBID"] = "%s.%d" % (args.pool, idx)
                if not args.command_output:
                    out_fd = open(
                        os.path.join(args.top_dir, "log", args.pool, str(idx)), "w"
                    )
                    out_fd.write("+ cd " + data["wd"] + "\n")
                    out_fd.write("+ " + " ".join(data["real_cmd"]) + "\n")
                    out_fd.flush()
                    proc = subprocess.Popen(
                        data["real_cmd"], stdout=out_fd, stderr=out_fd
                    )
                else:
                    out_fd = None
                    proc = subprocess.Popen(data["real_cmd"])
                if proc:
                    data["pid"] = proc.pid
                    commands.append([res, proc, out_fd, data["real_cmd"], idx, to_exec])
                with open(to_exec, "w") as f:
                    json.dump(data, f)
            except Exception:
                log.exception("Unable to execute command")
                free_resource(res, args)
                log.debug("Removing %s" % to_exec)
                os.remove(to_exec)

    if commands != []:
        log.info("Waiting for commands: %s" % commands)

        number = len(commands)
        while number > 0:
            log.debug("Waiting %d commands" % number)
            status = os.wait()
            for res, proc, fd, cmd, idx, to_exec in commands:
                if proc and proc.pid == status[0]:
                    number -= 1
                    break
            else:
                continue
            if proc:
                proc.wait()
                if fd:
                    fd.close()
                log.info("%s returned %d" % (cmd, os.WEXITSTATUS(status[1])))
                RET_CODE[idx] = os.WEXITSTATUS(status[1])
                log.debug("Removing %s" % to_exec)
                try:
                    os.remove(to_exec)
                except FileNotFoundError:
                    pass
            if res and args:
                free_resource(res, args)

    return 0


def book_resource(args):
    available_dir = os.path.join(args.top_dir, "available", args.pool)
    resources = [
        f
        for f in os.listdir(available_dir)
        if os.path.islink(os.path.join(available_dir, f))
    ]

    for res in resources:
        try:
            os.remove(os.path.join(available_dir, res))
            return res
        except FileNotFoundError:
            continue
    return None


def free_resource(res, args):
    path = os.path.join(args.top_dir, "pool", args.pool, res)
    # do not symlink if the resource has been removed during run
    if os.path.exists(path):
        symlink = os.path.join(args.top_dir, "available", args.pool, res)
        log.debug("Creating symlink %s" % symlink)
        os.symlink(path, symlink)


def get_command(args):
    seq = lib.Seq(args)

    seq.lock()
    first, next = seq.get()

    to_exec = None
    indice = None
    pri = -1
    # first pass to find the highest priority job
    for idx in range(first, next):
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, str(idx))
        if os.path.exists(cmdfile):
            log.debug("getting prority for %s" % cmdfile)
            with open(cmdfile) as cmdfd:
                data = json.load(cmdfd)
                priority = data["priority"] if "priority" in data else 0
                if priority > pri:
                    log.debug("top priority so far %s => %d" % (cmdfile, priority))
                    indice = idx
    if indice:
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, str(indice))
        movedfile = cmdfile + EXT
        os.rename(cmdfile, movedfile)
        to_exec = movedfile
        if indice == first:
            seq.set(indice + 1, next)

    seq.unlock()
    log.debug("get_command %s %s" % (to_exec, indice))
    return to_exec, indice


# run_cmd.py ends here
