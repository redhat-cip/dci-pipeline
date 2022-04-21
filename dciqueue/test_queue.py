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

import json
import os
import shutil
import tempfile
import time
import unittest
import uuid

from dciqueue import lib, main, run_cmd


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

    def dir_exists(self, directory, subdir):
        path = os.path.join(self.queue_dir, directory, subdir)
        self.assertTrue(os.path.exists(path) and os.path.isdir(path), path)

    def file_exists(self, directory, subdir, filename):
        path = os.path.join(self.queue_dir, directory, subdir, filename)
        self.assertTrue(os.path.exists(path) and os.path.isfile(path), path)

    def link_exists(self, directory, subdir, filename):
        path = os.path.join(self.queue_dir, directory, subdir, filename)
        self.assertTrue(os.path.exists(path) and os.path.islink(path), path)

    def doesnt_exist(self, directory, subdir, filename=None):
        if filename:
            path = os.path.join(self.queue_dir, directory, subdir, filename)
        else:
            path = os.path.join(self.queue_dir, directory, subdir)
        self.assertFalse(os.path.exists(path), path)

    def test_add_pool(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        for key in lib.DIRS:
            self.dir_exists(key, "8nodes")

    def test_remove_pool(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(main.main(["dci-queue", "remove-pool", "-n", "8nodes"]), 0)
        for key in lib.DIRS:
            self.doesnt_exist(key, "8nodes")

    def test_add_resource(self):
        def validate(key, exist):
            path = os.path.join(self.queue_dir, key, "8nodes", "cluster4")
            if exist:
                self.assertTrue(os.path.exists(path) or os.path.islink(path), path)
            else:
                self.assertFalse(os.path.exists(path) or os.path.islink(path), path)

        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
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
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        with self.assertRaises(SystemExit):
            main.main(["dci-queue", "remove-resource", "8nodes", "cluster4"])
        self.assertEqual(
            main.main(
                [
                    "dci-queue",
                    "remove-resource",
                    "8nodes",
                    "cluster4",
                    "reserved to debug blabla (fred)",
                ]
            ),
            0,
        )
        for key in ("pool", "available"):
            self.doesnt_exist(key, "8nodes", "cluster4")
        self.file_exists("reason", "8nodes", "cluster4")
        self.assertEqual(main.main(["dci-queue", "list", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.doesnt_exist("reason", "8nodes", "cluster4")

    def test_schedule(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(
                ["dci-queue", "schedule", "-p", "1", "8nodes", "echo", "@RESOURCE"]
            ),
            0,
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
            data = json.load(open(path))
            self.assertIn("priority", data)
            self.assertEqual(data["priority"], 1 if seq == "1" else 0)
        self.doesnt_exist("queue", "8nodes", "3")

    def test_schedule_force(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
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
            self.file_exists("queue", "8nodes", seq)

    def test_schedule_remove(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "-r", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        self.doesnt_exist("pool", "8nodes", "cluster4")

    def test_unschedule(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "unschedule", "8nodes", "1"]), 0)
        self.assertEqual(main.main(["dci-queue", "unschedule", "8nodes", "1"]), 0)
        self.doesnt_exist("queue", "8nodes", "1")

    def test_schedule_block(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "-b", "8nodes", "false", "@RESOURCE"]),
            1,
        )

    def test_run(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(
            main.main(
                [
                    "dci-queue",
                    "schedule",
                    "-p",
                    "2",
                    "8nodes",
                    "echo",
                    "@RESOURCE",
                    "first",
                ]
            ),
            0,
        )
        self.assertEqual(
            main.main(
                [
                    "dci-queue",
                    "schedule",
                    "-p",
                    "2",
                    "8nodes",
                    "echo",
                    "@RESOURCE",
                    "second",
                ]
            ),
            0,
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        self.file_exists("queue", "8nodes", "1")
        self.doesnt_exist("queue", "8nodes", "2")
        self.file_exists("queue", "8nodes", "3")
        self.file_exists("available", "8nodes", "cluster4")
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        self.doesnt_exist("queue", "8nodes", "3")

    def test_env_vars(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
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
                    'test "$DCI_QUEUE_JOBID" = "8nodes.1" -a "$DCI_QUEUE" = "8nodes" -a "$DCI_QUEUE_ID" = "1" || exit 1; echo @RESOURCE',
                ]
            ),
            0,
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        self.assertEqual(run_cmd.RET_CODE[1], 0)

    def test_run_unschedule(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
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
        self.doesnt_exist("available", "8nodes", "cluster4")
        self.file_exists("queue", "8nodes", "1" + run_cmd.EXT)
        self.assertEqual(main.main(["dci-queue", "unschedule", "8nodes", "1"]), 0)
        time.sleep(5)
        self.file_exists("available", "8nodes", "cluster4")
        self.doesnt_exist("queue", "8nodes", "1" + run_cmd.EXT)

    def test_run_invalid_command(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
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
        self.doesnt_exist("queue", "8nodes", "1" + run_cmd.EXT)
        self.file_exists("available", "8nodes", "cluster4")

    def test_run_no_resource(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        self.file_exists("queue", "8nodes", "1")

    def test_list(self):
        import io
        from contextlib import redirect_stdout

        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)

        with io.StringIO() as buf, redirect_stdout(buf):
            rc = main.main(["dci-queue", "list"])
            output = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("8nodes", output)

        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "list", "8nodes"]), 0)
        self.assertEqual(main.main(["dci-queue", "remove-pool", "-n", "8nodes"]), 0)

        with io.StringIO() as buf, redirect_stdout(buf):
            rc = main.main(["dci-queue", "list"])
            output = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("No pool was found", output)

    def test_log_level(self):
        self.assertEqual(
            main.main(["dci-queue", "-l", "CRITICAL", "add-pool", "-n", "8nodes"]), 0
        )
        with self.assertRaises(SystemExit):
            main.main(["dci-queue", "-l", "TOTO", "add-pool", "-n", "8nodes"])

    def test_log(self):
        self.assertEqual(main.main(["dci-queue", "log", "8nodes", "1"]), 1)
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
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
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
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
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-resource", "8nodes", "cluster4"]), 0
        )
        os.chdir("/tmp")
        self.assertEqual(
            main.main(["dci-queue", "schedule", "8nodes", "echo", "@RESOURCE"]), 0
        )
        self.assertEqual(main.main(["dci-queue", "searchdir", "8nodes", "/tmp"]), 0)

    def test_dci_job(self):
        import io
        from contextlib import redirect_stdout

        job_id = uuid.uuid4()
        job_name = "test-dci-job"
        job_ids = "%s:%s" % (job_name, job_id)
        res = "res"
        with open(os.path.join(self.queue_dir, res), "w") as f:
            f.write("- Scheduled DCI job %s\n" % job_id)
            f.write("- Setting tag job:%s on job %s\n" % (job_name, job_id))
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(main.main(["dci-queue", "add-resource", "8nodes", res]), 0)
        main.main(
            [
                "dci-queue",
                "schedule",
                "8nodes",
                "cat",
                os.path.join(self.queue_dir, "@RESOURCE"),
            ]
        )
        self.assertEqual(main.main(["dci-queue", "run", "8nodes"]), 0)
        with io.StringIO() as buf, redirect_stdout(buf):
            rc = main.main(["dci-queue", "dci-job", "8nodes", "1"])
            output = buf.getvalue()
        self.assertEqual(rc, 0)
        self.assertEqual(output, job_ids)

    def test_add_crontab(self):
        crontab_file = os.path.join(self.queue_dir, "crontab")
        with open(crontab_file, "w"):
            pass
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(
            main.main(["dci-queue", "add-crontab", "8nodes", crontab_file]), 0
        )
        self.assertEqual(
            main.main(["dci-queue", "remove-crontab", "8nodes", crontab_file]), 0
        )

    def test_clean(self):
        self.assertEqual(main.main(["dci-queue", "add-pool", "-n", "8nodes"]), 0)
        self.assertEqual(main.main(["dci-queue", "add-resource", "8nodes", "res"]), 0)
        os.unlink(os.path.join(self.queue_dir, "available", "8nodes", "res"))
        self.doesnt_exist("available", "8nodes", "res")
        execfile = os.path.join(self.queue_dir, "queue", "8nodes", "1234" + run_cmd.EXT)
        with open(execfile, "w") as fd:
            json.dump({"resource": "res", "pid": 123456}, fd)
        self.assertEqual(main.main(["dci-queue", "clean", "8nodes"]), 0)
        self.doesnt_exist("queue", "8nodes", "1234" + run_cmd.EXT)
        self.file_exists("available", "8nodes", "res")


if __name__ == "__main__":
    unittest.main()

# test_queue.py ends here
