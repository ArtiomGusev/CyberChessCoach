# seca/simre/telemetry.py


class MetaDataset:
    def __init__(self):
        self.records = []

    def add(self, state, action, outcome):
        self.records.append((state, action, outcome))

    def sample(self, n=128):
        import random

        return random.sample(self.records, min(n, len(self.records)))
