# seca/simre/hypothesis.py

class Hypothesis:
    def __init__(self, name, modify_fn):
        self.name = name
        self.modify_fn = modify_fn  # modifies curriculum/policy
        self.score = None
