import math
import numpy as np


class Node:
    def __init__(self, state, parent=None, action=None):
        self.state = state
        self.parent = parent
        self.action = action

        self.children = []
        self.visits = 0
        self.value = 0.0
        self.uncertainty = 0.0


class SECA_MCTS:
    def __init__(self, world_model, actions, c_explore=1.4, c_uncert=0.5):
        self.world_model = world_model
        self.actions = actions
        self.c_explore = c_explore
        self.c_uncert = c_uncert

    # ---------------------------------
    # Selection with uncertainty-UCB
    # ---------------------------------
    def select(self, node: Node):
        while node.children:
            node = max(
                node.children,
                key=lambda n: self.ucb(node, n),
            )
        return node

    def ucb(self, parent: Node, child: Node):
        if child.visits == 0:
            return float("inf")

        exploit = child.value / child.visits
        explore = self.c_explore * math.sqrt(math.log(parent.visits) / child.visits)
        uncert = self.c_uncert * child.uncertainty

        return exploit + explore + uncert

    # ---------------------------------
    # Expansion
    # ---------------------------------
    def expand(self, node: Node):
        for action in self.actions:
            next_state, unc = self.simulate_transition(node.state, action)

            child = Node(next_state, parent=node, action=action)
            child.uncertainty = unc
            node.children.append(child)

    # ---------------------------------
    # Simulation via world model
    # ---------------------------------
    def simulate_transition(self, state, action):
        features = self.encode(state, action)

        r, c, r_unc, c_unc = self.world_model.predict(features)

        next_state = np.array([
            state[0] + r,
            state[1] + c,
        ])

        uncertainty = r_unc + c_unc
        return next_state, uncertainty

    # ---------------------------------
    # Backpropagation
    # ---------------------------------
    def backprop(self, node: Node, reward: float):
        while node:
            node.visits += 1
            node.value += reward
            node = node.parent

    # ---------------------------------
    # One MCTS search
    # ---------------------------------
    def search(self, root_state, simulations=50):
        root = Node(root_state)

        for _ in range(simulations):
            leaf = self.select(root)

            if leaf.visits > 0:
                self.expand(leaf)
                leaf = leaf.children[0]

            reward = self.evaluate(leaf.state)
            self.backprop(leaf, reward)

        best = max(root.children, key=lambda n: n.visits)
        return best.action

    # ---------------------------------
    # Reward evaluation
    # ---------------------------------
    def evaluate(self, state):
        return state[0] + 0.3 * state[1]

    # ---------------------------------
    # Feature encoder
    # ---------------------------------
    def encode(self, state, action):
        return np.array([state[0], state[1], action])
