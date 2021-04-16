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

import json
import os
import shutil
import tempfile
import time
import unittest

from dciqueue import main
from dciqueue import run_cmd


class TestQueue(unittest.TestCase):
    def setUp(self):
        self.queue_dir = tempfile.mkdtemp()
        os.environ["DCI_QUEUE_DIR"] = self.queue_dir
        os.environ["DCI_QUEUE_LOG_LEVEL"] = "DEBUG"
        os.environ["DCI_QUEUE_CONSOLE_OUTPUT"] = "t"

    def tearDown(self):
        shutil.rmtree(self.queue_dir)

    def call(self, arg, stdout=None, stderr=None, *args, **kwargs):
        self.arg = arg
        if stdout:
            stdout.close()
        if stderr:
            stderr.close()
        return None

    def fork(self, arg, *args, **kwargs):
        self.arg = arg

    def test_add_pool(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        for key in ("pool", "queue", "available", "log"):
            path = os.path.join(self.queue_dir, key, "8nodes")
            self.assertTrue(os.path.exists(path) and os.path.isdir(path), path)

    def test_remove_pool(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(main.main(["dci-queue", "remove-pool", "8nodes"]), 0)
        for key in ("pool", "queue", "available", "log"):
            path = os.path.join(self.queue_dir, key, "8nodes")
            self.assertFalse(os.path.exists(path) and os.path.isdir(path), path)

    def test_add_resource(self):
        def validate(key, exist):
            path = os.path.join(self.queue_dir, key, "8nodes", "cluster4")
            if exist:
                self.assertTrue(os.path.exists(path) or os.path.islink(path), path)
            else:
                self.assertFalse(os.path.exists(path) or os.path.islink(path), path)

        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        cmd = os.path.join(self.queue_dir, "queue", "8nodes", "1" + run_cmd.EXT)
        with open(cmd, "w") as fd:
            json.dump({"resource": "cluster4"}, fd)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        for key, exist in (("pool", True), ("available", False)):
            validate(key, exist)
        os.unlink(cmd)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        for key, exist in (("pool", True), ("available", True)):
            validate(key, exist)

    def test_remove_resource(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "remove-resource", "8nodes", "cluster4"]), 0
        )
        for key in ("pool", "available"):
            path = os.path.join(self.queue_dir, key, "8nodes", "cluster4")
            self.assertFalse(os.path.exists(path) or os.path.islink(path), path)

    def test_schedule(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "ls", "/etc/@RESOURCE"]), 0
        )
        for seq in ("1", "2"):
            path = os.path.join(self.queue_dir, "queue", "8nodes", seq)
            self.assertTrue(os.path.exists(path) and os.path.isfile(path), path)
        path = os.path.join(self.queue_dir, "queue", "8nodes", "3")
        self.assertFalse(os.path.exists(path) and os.path.isfile(path), path)

    def test_schedule_force(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "-f", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "-f", "8nodes", "echo", "@RESOURCE"]), 0
        )
        for seq in ("1", "2"):
            path = os.path.join(self.queue_dir, "queue", "8nodes", seq)
            self.assertTrue(os.path.exists(path) and os.path.isfile(path), path)

    def test_schedule_remove(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "-r", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        path = os.path.join(self.queue_dir, "pool", "8nodes", "cluster4")
        self.assertFalse(os.path.exists(path), path)

    def test_unschedule(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "unschedule", "8nodes", "1"]), 0)
        self.assertEqual(main.main(["dci-queue", "unschedule", "8nodes", "1"]), 0)
        path = os.path.join(self.queue_dir, "queue", "8nodes", "1")
        self.assertFalse(os.path.exists(path) and os.path.isfile(path), path)

    def test_schedule_block(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "-b", "8nodes", "false", "@RESOURCE"]),
            1,
        )

    def test_run(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        path = os.path.join(self.queue_dir, "queue", "8nodes", "1")
        self.assertFalse(os.path.exists(path), path)
        path = os.path.join(self.queue_dir, "available", "8nodes", "cluster4")
        self.assertTrue(os.path.exists(path), path)

    def test_jobid(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(
                [
                    "dci-queue",
                    "schedule",
                    "8nodes",
                    "--",
                    "bash",
                    "-c",
                    'test -n "$DCI_QUEUE_JOBID" || exit 1; echo @RESOURCE',
                ]
            ),
            0,
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        self.assertEqual(run_cmd.RET_CODE[1], 0)

    def test_run_unschedule(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(
                [
                    "dci-queue",
                    "schedule",
                    "8nodes",
                    "--",
                    "bash",
                    "-c",
                    "sleep 3000; echo @RESOURCE",
                ]
            ),
            0,
        )
        os.system("dci-queue run 8nodes &")
        time.sleep(5)
        res_file = os.path.join(self.queue_dir, "available", "8nodes", "cluster4")
        job_file = os.path.join(self.queue_dir, "queue", "8nodes", "1" + run_cmd.EXT)
        self.assertFalse(os.path.exists(res_file), res_file)
        self.assertTrue(os.path.exists(job_file), job_file)
        self.assertEqual(main.main(["dci-queue", "unschedule", "8nodes", "1"]), 0)
        time.sleep(5)
        self.assertFalse(os.path.exists(job_file), job_file)
        self.assertTrue(os.path.exists(res_file), res_file)

    def test_run_invalid_command(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(
                ["dci-queue", "schedule", "8nodes", "no-such-command", "@RESOURCE"]
            ),
            0,
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        path = os.path.join(self.queue_dir, "queue", "8nodes", "1" + run_cmd.EXT)
        self.assertFalse(os.path.exists(path), path)
        path = os.path.join(self.queue_dir, "available", "8nodes", "cluster4")
        self.assertTrue(os.path.exists(path), path)

    def test_run_no_resource(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        path = os.path.join(self.queue_dir, "queue", "8nodes", "1")
        self.assertTrue(os.path.exists(path), path)

    def test_list(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "list", "8nodes"]), 0)

    def test_log_level(self):
        self.assertEqual(
            main.main(["dci-queue", "-l", "CRITICAL", "add-pool", "8nodes"]), 0
        )
        with self.assertRaises(SystemExit):
            main.main(["dci-queue", "-l", "TOTO", "add-pool", "8nodes"])

    def test_log(self):
        self.assertEqual(main.main(["dci-queue", "log", "8nodes", "1"]), 1)
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        saved = os.execlp
        os.execlp = self.fork
        main.main(["dci-queue", "log", "8nodes", "1"])
        self.assertEqual(self.arg, "tail")
        os.execlp = saved

    def test_search(self):
        self.assertEqual(main.main(["dci-queue", "log", "8nodes", "1"]), 1)
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "search", "8nodes", "echo", "@RESOURCE"]), 0
        )

    def test_searchdir(self):
        self.assertEqual(main.main(["dci-queue", "log", "8nodes", "1"]), 1)
        self.assertEqual(main.main(["dci-queue", "add-pool", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        os.chdir("/tmp")
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "searchdir", "8nodes", "/tmp"]), 0)


if __name__ == "__main__":
    unittest.main()

# test_queue.py ends here
