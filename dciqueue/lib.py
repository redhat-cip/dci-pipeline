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

import fcntl
import logging
import os
import time

log = logging.getLogger(__name__)


class Seq(object):
    def __init__(self, args):
        self.args = args

    def lock(self):
        self.seqfile_lck = os.path.join(self.args.top_dir, 'queue', self.args.pool, '.seq.lck')
        self.lock_fd = open(self.seqfile_lck, 'w')
        while True:
            try:
                fcntl.lockf(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except IOError:
                log.debug("Another instance is already running, waiting 10 sec...")
                time.sleep(10)

    def unlock(self):
        fcntl.lockf(self.lock_fd, fcntl.LOCK_UN)
        self.lock_fd.close()

    def get(self):
        seqfile = os.path.join(self.args.top_dir, 'queue', self.args.pool, '.seq')
        with open(seqfile) as f:
            seq = int(f.read(-1))
        log.debug('Read seq file %s: %d' % (seqfile, seq))
        return seq

    def set(self, seq):
        seqfile = os.path.join(self.args.top_dir, 'queue', self.args.pool, '.seq')
        with open(seqfile, 'w') as f:
            f.write(str(seq))
        log.debug('Updated seq file %s to %d' % (seqfile, seq))


def get_seq(args):
    seq_obj = Seq(args)
    seq_obj.lock()
    seq = seq_obj.get()
    seq_obj.unlock()
    return seq


def inc_seq(args):
    seq_obj = Seq(args)
    seq_obj.lock()
    seq = seq_obj.get()
    seq += 1
    seq_obj.set(seq)
    seq_obj.unlock()
    return seq

# lib.py ends here
