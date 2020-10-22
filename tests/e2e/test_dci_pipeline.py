#
# Copyright (C) Red Hat, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from dciclient.v1.api import context as dci_context
from dciclient.v1.api import job as dci_job

import os
import subprocess
import time


_working_directory = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_dci_pipeline():
    admin_context = dci_context.build_dci_context(
        dci_login='admin',
        dci_password='admin',
        dci_cs_url='http://127.0.0.1:5000/')
    len_jobs_1 = len(dci_job.list(admin_context).json()['jobs'])
    _command = 'dci-pipeline'
    proc = subprocess.Popen(_command, shell=True, cwd=_working_directory)
    while True:
        try:
            print('waiting for dci-pipeline')
            proc.communicate(timeout=1)
            break
        except subprocess.TimeoutExpired:
            time.sleep(1)
    len_jobs_2 = len(dci_job.list(admin_context).json()['jobs'])
    assert (len_jobs_1 + 2) == len_jobs_2
