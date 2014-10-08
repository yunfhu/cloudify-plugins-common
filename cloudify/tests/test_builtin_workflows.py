#########
# Copyright (c) 2014 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#  * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  * See the License for the specific language governing permissions and
#  * limitations under the License.


import unittest
import os
import time

from cloudify.workflows import local
from cloudify.decorators import operation


class TestBuiltinWorkflows(unittest.TestCase):

    def setUp(self):
        blueprint_path = os.path.join(
            os.path.dirname(os.path.realpath(__file__)),
            "resources/blueprints/execute_operation.yaml")
        self.env = local.init_env(blueprint_path)

    def test_execute_operation(self):
        params = self._get_params()
        self.env.execute('execute_operation', params)
        self._make_filter_assertions(4)

    def test_execute_operation_default_values(self):
        params = {'operation': 'cloudify.interfaces.lifecycle.create'}
        self.env.execute('execute_operation', params)
        self._make_filter_assertions(4)

    def test_execute_operation_with_operation_parameters(self):
        operation_param_key = 'operation_param_key'
        operation_param_value = 'operation_param_value'
        op_params = {operation_param_key: operation_param_value}

        params = self._get_params(op_params=op_params)
        self.env.execute('execute_operation', params)
        self._make_filter_assertions(4)

        instances = self.env.storage.get_node_instances()
        for instance in instances:
            self.assertIn(operation_param_key, instance.runtime_properties)
            self.assertEquals(operation_param_value,
                              instance.runtime_properties[operation_param_key])

    def test_execute_operation_by_nodes(self):
        node_ids = ['node2', 'node3']
        params = self._get_params(node_ids=node_ids)
        self.env.execute('execute_operation', params)
        self._make_filter_assertions(3, node_ids=node_ids)

    def test_execute_operation_by_node_instances(self):
        instances = self.env.storage.get_node_instances()
        node_instance_ids = [instances[0].id, instances[3].id]
        params = self._get_params(node_instance_ids=node_instance_ids)
        self.env.execute('execute_operation', params)
        self._make_filter_assertions(2, node_instance_ids=node_instance_ids)

    def test_execute_operation_by_type_names(self):
        type_names = ['mock_type2']
        params = self._get_params(type_names=type_names)
        self.env.execute('execute_operation', params)
        self._make_filter_assertions(3, type_names=type_names)

    def test_execute_operation_by_nodes_and_types(self):
        pass

    def test_execute_operation_by_nodes_types_and_node_instances(self):
        pass

    def test_execute_operation_empty_intersection(self):
        pass

    def test_execute_operation_with_dependency_order(self):
        pass

    def _make_filter_assertions(self, expected_num_of_visited_instances,
                                node_ids=None, node_instance_ids=None,
                                type_names=None):
        num_of_visited_instances = 0
        instances = self.env.storage.get_node_instances()
        nodes_by_id = {node.id: node for node in self.env.storage.get_nodes()}

        for inst in instances:
            test_op_visited = inst.runtime_properties.get('test_op_visited')

            if (not node_ids or inst.node_id in node_ids) \
                and \
                (not node_instance_ids or inst.id in node_instance_ids) \
                and \
                (not type_names or (next(type for type in nodes_by_id[
                    inst.node_id].type_hierarchy if type in type_names),
                                    None)):
                self.assertTrue(test_op_visited)
                num_of_visited_instances += 1
            else:
                self.assertIsNone(test_op_visited)

        # this is actually an assertion to ensure the tests themselves are ok
        self.assertEquals(expected_num_of_visited_instances,
                          num_of_visited_instances)

    def _get_params(self, op='cloudify.interfaces.lifecycle.create',
                    op_params=None, run_by_dep=False, node_ids=None,
                    node_instance_ids=None, type_names=None):
        return {
            'operation': op,
            'operation_kwargs': op_params or {},
            'run_by_dependency_order': run_by_dep,
            'node_ids': node_ids or [],
            'node_instance_ids': node_instance_ids or [],
            'type_names': type_names or []
        }


@operation
def exec_op_test_operation(ctx, **kwargs):
    ctx.runtime_properties['test_op_visited'] = True
    if kwargs:
        ctx.runtime_properties['op_kwargs'] = kwargs


@operation
def exec_op_dependency_order_test_operation(ctx, **kwargs):
    ctx.runtime_properties['visit_time'] = time.time()
    time.sleep(1)
