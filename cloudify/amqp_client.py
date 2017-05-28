########
# Copyright (c) 2013 GigaSpaces Technologies Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
#    * WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    * See the License for the specific language governing permissions and
#    * limitations under the License.

import json
import logging
import threading

import pika
import pika.exceptions

from cloudify import broker_config
from cloudify import cluster
from cloudify import exceptions
from cloudify import utils
from cloudify.constants import BROKER_PORT_SSL, BROKER_PORT_NO_SSL

logger = logging.getLogger(__name__)


class AMQPClient(object):

    EVENTS_EXCHANGE_NAME = 'cloudify-events'
    LOGS_EXCHANGE_NAME = 'cloudify-logs'
    channel_settings = {
        'auto_delete': False,
        'durable': True,
    }

    def __init__(self,
                 amqp_user,
                 amqp_pass,
                 amqp_host,
                 amqp_vhost,
                 ssl_enabled,
                 ssl_cert_path):
        self.connection = None
        self.channel = None
        self._is_closed = False
        credentials = pika.credentials.PlainCredentials(
            username=amqp_user,
            password=amqp_pass)
        ssl_options = utils.internal.get_broker_ssl_options(ssl_enabled,
                                                            ssl_cert_path)
        self._connection_parameters = pika.ConnectionParameters(
            host=amqp_host,
            port=BROKER_PORT_SSL if ssl_enabled else BROKER_PORT_NO_SSL,
            virtual_host=amqp_vhost,
            credentials=credentials,
            ssl=bool(ssl_enabled),
            ssl_options=ssl_options)
        self._connect()

    def _connect(self):
        self.connection = pika.BlockingConnection(self._connection_parameters)
        self.channel = self.connection.channel()
        self.channel.confirm_delivery()
        for exchange in [self.EVENTS_EXCHANGE_NAME, self.LOGS_EXCHANGE_NAME]:
            self.channel.exchange_declare(exchange=exchange, type='fanout',
                                          **self.channel_settings)

    def publish_message(self, message, message_type):
        if self._is_closed:
            raise exceptions.ClosedAMQPClientException(
                'Publish failed, AMQP client already closed')
        if message_type == 'event':
            exchange = self.EVENTS_EXCHANGE_NAME
        else:
            exchange = self.LOGS_EXCHANGE_NAME
        routing_key = ''
        body = json.dumps(message)
        try:
            self.channel.basic_publish(exchange=exchange,
                                       routing_key=routing_key,
                                       body=body)
        except pika.exceptions.ConnectionClosed as e:
            logger.warn(
                'Connection closed unexpectedly for thread {0}, '
                'reconnecting. ({1}: {2})'
                .format(threading.current_thread(), type(e).__name__, repr(e)))
            # obviously, there is no need to close the current
            # channel/connection.
            self._connect()
            self.channel.basic_publish(exchange=exchange,
                                       routing_key=routing_key,
                                       body=body)

    def close(self):
        if self._is_closed:
            return
        self._is_closed = True
        thread = threading.current_thread()
        if self.channel:
            logger.debug('Closing amqp channel of thread {0}'.format(thread))
            try:
                self.channel.close()
            except Exception as e:
                # channel might be already closed, log and continue
                logger.debug('Failed to close amqp channel of thread {0}, '
                             'reported error: {1}'.format(thread, repr(e)))

        if self.connection:
            logger.debug('Closing amqp connection of thread {0}'
                         .format(thread))
            try:
                self.connection.close()
            except Exception as e:
                # connection might be already closed, log and continue
                logger.debug('Failed to close amqp connection of thread {0}, '
                             'reported error: {1}'.format(thread, repr(e)))


def create_client(amqp_host=None,
                  amqp_user=None,
                  amqp_pass=None,
                  amqp_vhost=None,
                  ssl_enabled=None,
                  ssl_cert_path=None):
    thread = threading.current_thread()

    # there's 3 possible sources of the amqp settings: passed in arguments,
    # current cluster active manager (if any), and broker_config; use the first
    # that is defined, in that order
    defaults = {
        'amqp_host': broker_config.broker_hostname,
        'amqp_user': broker_config.broker_username,
        'amqp_pass': broker_config.broker_password,
        'amqp_vhost': broker_config.broker_vhost,
        'ssl_enabled': broker_config.broker_ssl_enabled,
        'ssl_cert_path': broker_config.broker_cert_path
    }
    defaults.update(cluster.get_cluster_amqp_settings())
    amqp_settings = {
        'amqp_user': amqp_user or defaults['amqp_user'],
        'amqp_host': amqp_host or defaults['amqp_host'],
        'amqp_pass': amqp_pass or defaults['amqp_pass'],
        'amqp_vhost': amqp_vhost or defaults['amqp_vhost'],
        'ssl_enabled': ssl_enabled or defaults['ssl_enabled'],
        'ssl_cert_path': ssl_cert_path or defaults['ssl_cert_path']
    }

    try:
        client = AMQPClient(**amqp_settings)
        logger.debug('AMQP client created for thread {0}'.format(thread))
    except Exception as e:
        logger.warning(
            'Failed to create AMQP client for thread: {0} ({1}: {2})'
            .format(thread, type(e).__name__, e))
        raise
    return client
