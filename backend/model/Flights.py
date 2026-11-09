from torch import nn

class FlightNetwork(nn.Module):
    def __init__(self):
        super().__init__()
        self.network = nn.Sequential(
            nn.Linear(37, 256),
            nn.ReLU(),
            nn.Linear(256, 256),
            nn.ReLU(),
            nn.Linear(256,1)
            # nn.ReLU(),
            # nn.Linear(64,1)
        )

    def forward(self, x):
        return self.network(x)