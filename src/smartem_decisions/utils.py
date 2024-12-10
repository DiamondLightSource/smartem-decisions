import os, yaml


def load_conf():
    with open(os.path.join(os.path.dirname(__file__), "config.yaml"), "r") as f:
        conf = yaml.safe_load(f.read())
    return conf
