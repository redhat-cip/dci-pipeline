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

import os
import shutil
import tempfile
import unittest

from dciqueue import main


class TestQueue(unittest.TestCase):

    def setUp(self):
        self.queue_dir = tempfile.mkdtemp()
        os.environ['QUEUE_DIR'] = self.queue_dir
        os.environ['QUEUE_LOG_LEVEL'] = 'DEBUG'

    def tearDown(self):
        shutil.rmtree(self.queue_dir)

    def test_add_pool(self):
        self.assertEqual(main.main(['queue', 'add-pool', '8nodes']), 0)
        self.assertEqual(main.main(['queue', 'add-pool', '8nodes']), 0)

if __name__ == "__main__":
    unittest.main()

# test_queue.py ends here
