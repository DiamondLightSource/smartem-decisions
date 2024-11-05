from argparse import ArgumentParser
from collections.abc import Sequence

from . import __version__

__all__ = ["main"]


def main(args: Sequence[str] | None = None) -> None:
    """Argument parser for the CLI."""
    parser = ArgumentParser()
    parser.add_argument(
        "-v",
        "--version",
        action="version",
        version=__version__,
    )
    parser.parse_args(args)


if __name__ == "__main__":
    main()


# from rabbitmq import RabbitMQ
# import sys
#
# def callback(ch, method, properties, body):
#     print(f"Received message: {body}")
#
# def main():
#     rabbitmq = RabbitMQ()
#     try:
#         print("Connection to RabbitMQ established successfully.")
#         rabbitmq.consume(queue_name='test_queue', callback=callback)
#     except Exception as e:
#         print(f"Failed to establish connection to RabbitMQ: {e}")
#         sys.exit(1)
#     finally:
#         rabbitmq.close()
#
# if __name__ == "__main__":
#     main()
