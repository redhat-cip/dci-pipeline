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

import logging
import os
import shutil
import tempfile
import time
import unittest

from dciqueue import lib

logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(process)d - %(levelname)s - %(message)s",
)


class Args(object):
    def __init__(self, pool):
        self.pool = pool
        self.top_dir = '/tmp/topdir'
        try:
            os.makedirs(os.path.join(self.top_dir, 'queue', self.pool))
        except:
            pass

class TestLib(unittest.TestCase):

    def setUp(self):
        self.args = Args('pool')
        os.environ['QUEUE_DIR'] = self.args.top_dir

    def test_seq(self):
        if os.fork() != 0:
            time.sleep(10)
        obj = lib.Seq(self.args)
        obj.lock()
        logging.debug('doing some stuff while having the lock')
        time.sleep(20)
        obj.unlock()

if __name__ == "__main__":
    unittest.main()

# test_lib.py ends here
