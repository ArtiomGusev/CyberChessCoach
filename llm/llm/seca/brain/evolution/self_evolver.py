class SelfEvolver:
    """
    Controls safe self-improvement of SECA.
    """

    def __init__(self, researcher, judge, deployer):
        self.researcher = researcher
        self.judge = judge
        self.deployer = deployer

    def evolve_once(self, metrics):
        # 1. propose candidate architecture
        candidate = self.researcher.propose(metrics)

        # 2. evaluate in sandbox
        report = self.judge.evaluate(candidate)

        # 3. deploy only if strictly better
        if report["is_better"] and report["is_safe"]:
            self.deployer.deploy(candidate)
            return "upgraded"

        return "rejected"
