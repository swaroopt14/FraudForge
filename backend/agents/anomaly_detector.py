"""Autoencoder for zero-day / novel fraud scoring (Torch if present, else sklearn)."""

from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
from sklearn.neural_network import MLPRegressor

from config import AUTOENCODER_PATH, FEATURE_COLUMNS


def _try_torch():
    try:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset

        return torch, nn, DataLoader, TensorDataset
    except Exception:  # noqa: BLE001
        return None


_TORCH = _try_torch()


if _TORCH:
    torch, nn, DataLoader, TensorDataset = _TORCH

    class Autoencoder(nn.Module):
        def __init__(self, input_dim: int) -> None:
            super().__init__()
            hidden = min(64, max(16, input_dim))
            self.encoder = nn.Sequential(
                nn.Linear(input_dim, hidden),
                nn.ReLU(),
                nn.Linear(hidden, hidden // 2),
                nn.ReLU(),
                nn.Linear(hidden // 2, max(8, hidden // 4)),
            )
            self.decoder = nn.Sequential(
                nn.Linear(max(8, hidden // 4), hidden // 2),
                nn.ReLU(),
                nn.Linear(hidden // 2, hidden),
                nn.ReLU(),
                nn.Linear(hidden, input_dim),
            )

        def forward(self, x):
            return self.decoder(self.encoder(x))
else:
    Autoencoder = None  # type: ignore[misc, assignment]


class AnomalyDetector:
    def __init__(self, input_dim: int | None = None) -> None:
        self.input_dim = input_dim or len(FEATURE_COLUMNS)
        self.backend = "torch" if _TORCH else "sklearn"
        self.model = None
        self.threshold: float | None = None
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None
        if self.backend == "torch":
            torch, nn, *_ = _TORCH
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            self.model = Autoencoder(self.input_dim).to(self.device)
            self.optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-3)
            self.criterion = nn.MSELoss(reduction="none")
        else:
            self.model = MLPRegressor(
                hidden_layer_sizes=(64, 32, 16, 32, 64),
                activation="relu",
                solver="adam",
                max_iter=20,
                random_state=42,
                warm_start=True,
            )

    def _normalize(self, X: np.ndarray) -> np.ndarray:
        if self.mean is None or self.std is None:
            self.mean = X.mean(axis=0)
            self.std = np.clip(X.std(axis=0), 1e-6, None)
        return (X - self.mean) / self.std

    def train(
        self,
        X: np.ndarray,
        epochs: int = 20,
        batch_size: int = 256,
        subsample: int | None = 50_000,
        seed: int = 42,
    ) -> float:
        rng = np.random.default_rng(seed)
        X = np.asarray(X, dtype=np.float32)
        if subsample and len(X) > subsample:
            idx = rng.choice(len(X), size=subsample, replace=False)
            X = X[idx]
        Xn = self._normalize(X).astype(np.float32)

        if self.backend == "torch":
            torch, nn, DataLoader, TensorDataset = _TORCH
            tensor = torch.from_numpy(Xn)
            loader = DataLoader(TensorDataset(tensor), batch_size=batch_size, shuffle=True)
            self.model.train()
            for epoch in range(epochs):
                total = 0.0
                n_batches = 0
                for (batch,) in loader:
                    batch = batch.to(self.device)
                    self.optimizer.zero_grad()
                    recon = self.model(batch)
                    loss = self.criterion(recon, batch).mean()
                    loss.backward()
                    self.optimizer.step()
                    total += float(loss.item())
                    n_batches += 1
                if (epoch + 1) % 5 == 0 or epoch == 0:
                    print(f"Autoencoder epoch {epoch + 1}/{epochs} loss={total / max(n_batches, 1):.6f}")
        else:
            self.model.max_iter = max(epochs, 10)
            self.model.fit(Xn, Xn)
            print("Sklearn MLP autoencoder fitted")

        errors = self.predict(X)
        self.threshold = float(np.percentile(errors, 95))
        return self.threshold

    def predict(self, X: np.ndarray) -> np.ndarray:
        X = np.asarray(X, dtype=np.float32)
        Xn = self._normalize(X).astype(np.float32)
        if self.backend == "torch":
            torch, *_ = _TORCH
            self.model.eval()
            with torch.no_grad():
                tensor = torch.from_numpy(Xn).to(self.device)
                recon = self.model(tensor)
                err = ((recon - tensor) ** 2).mean(dim=1).cpu().numpy()
            return err
        recon = self.model.predict(Xn)
        return ((recon - Xn) ** 2).mean(axis=1)

    def is_anomaly(self, X: np.ndarray) -> np.ndarray:
        if self.threshold is None:
            raise RuntimeError("Anomaly detector has no threshold; train first")
        return (self.predict(X) > self.threshold).astype(int)

    def save(self, path: Path | None = None) -> Path:
        path = path or AUTOENCODER_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "backend": self.backend,
            "input_dim": self.input_dim,
            "threshold": self.threshold,
            "mean": self.mean,
            "std": self.std,
        }
        if self.backend == "torch":
            import torch

            payload["state_dict"] = self.model.state_dict()
            torch.save(payload, path)
        else:
            payload["model"] = self.model
            joblib.dump(payload, path.with_suffix(".pkl"))
            path.write_text("sklearn")
        return path

    @classmethod
    def load(cls, path: Path | None = None) -> "AnomalyDetector":
        path = path or AUTOENCODER_PATH
        pkl = path.with_suffix(".pkl")
        if pkl.exists():
            blob = joblib.load(pkl)
            det = cls(input_dim=int(blob["input_dim"]))
            det.backend = "sklearn"
            det.model = blob["model"]
            det.threshold = blob["threshold"]
            det.mean = blob["mean"]
            det.std = blob["std"]
            return det
        import torch

        blob = torch.load(path, map_location="cpu", weights_only=False)
        det = cls(input_dim=int(blob["input_dim"]))
        det.model.load_state_dict(blob["state_dict"])
        det.threshold = blob["threshold"]
        det.mean = blob["mean"]
        det.std = blob["std"]
        return det


__all__ = ["AnomalyDetector", "Autoencoder"]
