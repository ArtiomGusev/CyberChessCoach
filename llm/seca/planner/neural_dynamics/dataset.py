import torch
from torch.utils.data import Dataset


class SkillDynamicsDataset(Dataset):
    """
    Each sample:
        state_t
        action_id
        delta_skill
        next_conf
        next_fatigue
    """

    def __init__(self, samples):
        self.samples = samples

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        s, a, ds, nc, nf = self.samples[idx]

        return (
            torch.tensor(s, dtype=torch.float32),
            torch.tensor(a, dtype=torch.long),
            torch.tensor([ds], dtype=torch.float32),
            torch.tensor([nc], dtype=torch.float32),
            torch.tensor([nf], dtype=torch.float32),
        )
