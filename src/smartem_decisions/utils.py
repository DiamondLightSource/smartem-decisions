import os, yaml

def load_conf():
    # conf = yaml.safe_load(open(os.path.join(os.path.dirname(__file__), "config.yaml")))
    with open(os.path.join(os.path.dirname(__file__), "config.yaml"), 'r') as f:
        conf = yaml.safe_load(f.read())
    return conf
