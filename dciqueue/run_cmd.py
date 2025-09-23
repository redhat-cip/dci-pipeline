# -*- coding: utf-8 -*-
#
# Copyright (C) 2020-2025 Red Hat, Inc
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
    if not lib.check_pool(args.top_dir, args.pool):
        return 1

    commands = []
    skipped_jobs = set()  # Track jobs that have been skipped to avoid infinite loop

    while True:
        booked_resources = []

        # First, peek at the next job to check resource requirements
        to_exec, idx = peek_next_command(args)

        if not to_exec:
            log.debug("No command to run in pool %s" % args.pool)
            break
        else:
            # Check if we've already skipped this job to avoid infinite loop
            if idx in skipped_jobs:
                log.debug("All remaining jobs have been skipped, breaking loop")
                break

            with open(to_exec) as f:
                data = json.load(f)

            log.debug("Checking command %s" % data)

            # Check if extra resources are available BEFORE booking any resources
            extra_resources_available = True
            for pool in data["extra_pools"]:
                if not has_available_resource(args.top_dir, pool):
                    log.debug("No available resource in pool %s" % pool)
                    extra_resources_available = False
                    break

            # If extra resources are not available, skip this job
            if not extra_resources_available:
                log.debug("Skipping job due to unavailable extra resources")
                skipped_jobs.add(idx)
                continue

            # Now book the primary resource
            res = book_resource(args.top_dir, args.pool)

            if res is None:
                log.debug("No available resource anymore in pool %s" % args.pool)
                break
            log.debug("Booked resource %s in pool %s" % (res, args.pool))
            booked_resources.append((res, args.pool))

            # Now consume the job from the queue
            to_exec, idx = get_command(args)

            # book extra resources if needed
            extra_booking_failed = False
            for pool in data["extra_pools"]:
                extra_res = book_resource(args.top_dir, pool)
                if extra_res is None:
                    log.debug("No available resource anymore in pool %s" % pool)
                    free_resources(booked_resources, args.top_dir)
                    extra_booking_failed = True
                    break
                booked_resources.append((extra_res, pool))

            # If extra resource booking failed, skip this job and continue to next
            if extra_booking_failed:
                log.debug("Skipping job due to failed extra resource booking")
                continue

            data["real_cmd"] = [c.replace("@RESOURCE", res) for c in data["cmd"]]
            data["resource"] = res
            data["jobid"] = idx
            data["booked"] = booked_resources

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
                os.environ["DCI_QUEUE"] = args.pool
                os.environ["DCI_QUEUE_RES"] = res
                os.environ["DCI_QUEUE_ID"] = str(idx)
                os.environ["DCI_QUEUE_JOBID"] = "%s.%d" % (args.pool, idx)
                num = 1
                for r, p in booked_resources:
                    os.environ[f"DCI_QUEUE{num}"] = p
                    os.environ[f"DCI_QUEUE_RES{num}"] = r
                    num += 1
                if not args.command_output:
                    out_fd = open(
                        os.path.join(args.top_dir, "log", args.pool, str(idx)), "w"
                    )
                    # log environment variables
                    out_fd.write(f'+ DCI_QUEUE={os.environ["DCI_QUEUE"]}\n')
                    out_fd.write(f'+ DCI_QUEUE_RES={os.environ["DCI_QUEUE_RES"]}\n')
                    out_fd.write(f'+ DCI_QUEUE_ID={os.environ["DCI_QUEUE_ID"]}\n')
                    out_fd.write(f'+ DCI_QUEUE_JOBID={os.environ["DCI_QUEUE_JOBID"]}\n')
                    for idx in range(1, num):
                        out_fd.write(
                            f'+ DCI_QUEUE{idx}={os.environ[f"DCI_QUEUE{idx}"]}\n'
                        )
                        out_fd.write(
                            f'+ DCI_QUEUE_RES{idx}={os.environ[f"DCI_QUEUE_RES{idx}"]}\n'
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
                    commands.append(
                        [booked_resources, proc, out_fd, data["real_cmd"], idx, to_exec]
                    )
                with open(to_exec, "w") as f:
                    json.dump(data, f)
            except Exception:
                log.exception("Unable to execute command")
                free_resources(booked_resources, args.top_dir)
                log.debug("Removing %s" % to_exec)
                os.remove(to_exec)

    if commands != []:
        log.info("Waiting for commands: %s" % commands)

        number = len(commands)
        while number > 0:
            log.debug("Waiting %d commands" % number)
            status = os.wait()
            for booked, proc, fd, cmd, idx, to_exec in commands:
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
            if booked != [] and args:
                free_resources(booked, args.top_dir)
    return 0


def book_resource(top_dir, pool):
    """Book a resource from the pool.

    Removing the first symlink from the available directory.
    """
    available_dir = os.path.join(top_dir, "available", pool)
    resources = [
        f
        for f in os.listdir(available_dir)
        if os.path.islink(os.path.join(available_dir, f))
    ]

    for res in resources:
        try:
            filename = os.path.join(available_dir, res)
            os.remove(filename)
            log.debug("Removed symlink %s" % filename)
            return res
        except FileNotFoundError:
            continue
    return None


def free_resource(res, top_dir, pool):
    path = os.path.join(top_dir, "pool", pool, res)
    # do not symlink if the resource has been removed during run
    if os.path.exists(path):
        symlink = os.path.join(top_dir, "available", pool, res)
        log.debug("Creating symlink %s from pid %s" % (symlink, os.getpid()))
        os.symlink(path, symlink)


def free_resources(resources, top_dir):
    log.debug("Freeing resources: %s" % resources)
    for r, pool in resources:
        free_resource(r, top_dir, pool)


def peek_next_command(args):
    """Peek at the next command without consuming it from the queue."""
    seq = lib.Seq(args)

    seq.lock()
    first, next = seq.get()

    to_exec = None
    index = None
    pri = -1
    # first pass to find the highest priority job
    for idx in range(first, next):
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, str(idx))
        if os.path.exists(cmdfile):
            log.debug("getting priority for %s" % cmdfile)
            with open(cmdfile) as cmdfd:
                data = json.load(cmdfd)
                priority = data["priority"] if "priority" in data else 0
                if priority > pri:
                    log.debug("top priority so far %s => %d" % (cmdfile, priority))
                    index = idx
                    pri = priority
    if index is not None:
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, str(index))
        to_exec = cmdfile  # Don't move the file, just return the path

    seq.unlock()
    log.debug("peek_next_command %s %s" % (to_exec, index))
    return to_exec, index


def has_available_resource(top_dir, pool):
    """Check if there's at least one available resource in the pool."""
    available_dir = os.path.join(top_dir, "available", pool)
    if not os.path.exists(available_dir):
        return False

    resources = [
        f
        for f in os.listdir(available_dir)
        if os.path.islink(os.path.join(available_dir, f))
    ]
    return len(resources) > 0


def get_command(args):
    """Get the next command to execute from the queue."""
    seq = lib.Seq(args)

    seq.lock()
    first, next = seq.get()

    to_exec = None
    index = None
    pri = -1
    # first pass to find the highest priority job
    for idx in range(first, next):
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, str(idx))
        if os.path.exists(cmdfile):
            log.debug("getting priority for %s" % cmdfile)
            with open(cmdfile) as cmdfd:
                data = json.load(cmdfd)
                priority = data["priority"] if "priority" in data else 0
                if priority > pri:
                    log.debug("top priority so far %s => %d" % (cmdfile, priority))
                    index = idx
                    pri = priority
    if index is not None:
        cmdfile = os.path.join(args.top_dir, "queue", args.pool, str(index))
        movedfile = cmdfile + EXT
        os.rename(cmdfile, movedfile)
        to_exec = movedfile
        if index == first:
            seq.set(index + 1, next)

    seq.unlock()
    log.debug("get_command %s %s" % (to_exec, index))
    return to_exec, index


# run_cmd.py ends here
