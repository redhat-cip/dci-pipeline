# -*- coding: utf-8 -*-
#
# Copyright (C) Red Hat, Inc
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


import ansible_runner


def main():
    print('**** running ocp agent ****')
    ocp_extravars = {
        'DCI_CLIENT_ID': '',
        'DCI_API_SECRET': '',
        'DCI_CS_URL': 'https://api.distributed-ci.io/'
    }
    ocp_run = ansible_runner.run(
        private_data_dir="/home/yassine/dci/dci-pipeline/",
        playbook='/home/yassine/dci/dci-pipeline/dcipipeline/agents/openshift/agent.yml',
        verbosity=3,
        extravars=ocp_extravars)
    print(ocp_run.stats)

    print('\n\n**** running cnf agent ****')
    cnf_extravars = {
        'DCI_CLIENT_ID': '',
        'DCI_API_SECRET': '',
        'DCI_CS_URL': 'https://api.distributed-ci.io/',
        'OCP_CONFIG': {'master': 'master.example.com', 'worker': 'worker.example.com'}
    }
    cnf_run = ansible_runner.run(
        private_data_dir="/home/yassine/dci/dci-pipeline/",
        playbook='/home/yassine/dci/dci-pipeline/dcipipeline/agents/cnf/agent.yml',
        verbosity=3,
        extravars=cnf_extravars)
    print(cnf_run.stats)


if __name__ == '__main__':
    #pipeline_file = sys.argv[1]

    main()
