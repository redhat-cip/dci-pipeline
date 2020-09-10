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

import fcntl
import json
import logging
import os
import sys
import time

log = logging.getLogger(__name__)


class Seq(object):
    def __init__(self, args):
        self.seqfile = os.path.join(args.top_dir, "queue", args.pool, ".seq")

    def exists(self):
        return os.path.exists(self.seqfile)

    def lock(self):
        self.lock_fd = open(self.seqfile + ".lck", "w")
        while True:
            try:
                fcntl.lockf(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except IOError:
                log.debug("Another instance is already running, waiting 1 sec...")
                time.sleep(1)

    def unlock(self):
        fcntl.lockf(self.lock_fd, fcntl.LOCK_UN)
        self.lock_fd.close()

    def get(self):
        with open(self.seqfile) as f:
            seq = json.load(f)
        log.debug("Read seq file %s: %s" % (self.seqfile, seq))
        return seq["first"], seq["next"]

    def set(self, first, next):
        with open(self.seqfile, "w") as f:
            json.dump({"first": first, "next": next}, f)
        log.debug("Updated seq file %s to %d, %d" % (self.seqfile, first, next))


def get_seq(args):
    seq_obj = Seq(args)
    seq_obj.lock()
    first, next = seq_obj.get()
    seq_obj.unlock()
    return first, next


def check_pool(args):
    for key in ("pool", "queue", "available", "log"):
        d = os.path.join(args.top_dir, key, args.pool)
        if not os.path.exists(d):
            msg = "Directory %s doesn't exist. Use add-pool to create it." % (d,)
            log.error(msg)
            sys.stderr.write(msg)
            return False
    return True

# lib.py ends here
