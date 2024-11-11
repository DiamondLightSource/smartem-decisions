#!/usr/bin/env python

import os
import pika
import time

import yaml
from dotenv import load_dotenv
load_dotenv()

conf = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), 'config.yaml')))

connection = pika.BlockingConnection(
    pika.ConnectionParameters(
        host=os.getenv('RABBITMQ_HOST'),
        port=int(os.getenv('RABBITMQ_PORT')),
        credentials=pika.PlainCredentials(
            os.getenv('RABBITMQ_USER'),
            os.getenv('RABBITMQ_PASSWORD')
        )
    ))

channel = connection.channel()

channel.queue_declare(queue=conf['rabbitmq']['queue_name'], durable=True)
print(' [*] Waiting for messages. To exit press CTRL+C')


def callback(ch, method, properties, body):
    print(f" [x] Received message with props={properties} and body: {body.decode()}")
    time.sleep(body.count(b'.'))
    print(" [x] Done")
    ch.basic_ack(delivery_tag=method.delivery_tag)


channel.basic_qos(prefetch_count=1)
channel.basic_consume(queue=conf['rabbitmq']['queue_name'], on_message_callback=callback)

channel.start_consuming()
