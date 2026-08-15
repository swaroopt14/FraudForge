"""CTGAN (SDV or compact Torch GAN) with bootstrap fallback."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

from config import CTGAN_EPOCHS, CTGAN_PATH, PCA_FEATURES, RANDOM_STATE
from attack_catalog import VECTOR_TO_FAMILY
from features import FAMILY_TEMPLATES, MUTATION_CONTRACTS, overlay_family, overlay_legitimate

CTGAN_COLUMNS = [c for c in PCA_FEATURES if c != "Time"] + ["Time"]
LATENT_DIM = 16


def _json_num(value: Any) -> Any:
    if isinstance(value, (np.floating, float)):
        return float(value)
    if isinstance(value, (np.integer, int)):
        return int(value)
    if isinstance(value, (np.bool_, bool)):
        return bool(value)
    return value


class TorchCTGAN:
    """Conditional-free tabular GAN used when the SDV package is not installed."""

    def __init__(self, columns: list[str]) -> None:
        import torch
        import torch.nn as nn

        self.columns = columns
        self.device = torch.device("cpu")
        dim = len(columns)
        self.G = nn.Sequential(
            nn.Linear(LATENT_DIM, 64),
            nn.ReLU(),
            nn.Linear(64, 64),
            nn.ReLU(),
            nn.Linear(64, dim),
            nn.Tanh(),
        ).to(self.device)
        self.D = nn.Sequential(
            nn.Linear(dim, 64),
            nn.LeakyReLU(0.2),
            nn.Linear(64, 32),
            nn.LeakyReLU(0.2),
            nn.Linear(32, 1),
        ).to(self.device)
        self.mean: np.ndarray | None = None
        self.std: np.ndarray | None = None
        self._fitted = False

    def fit(self, df: pd.DataFrame, epochs: int = 50, batch_size: int = 64) -> None:
        import torch
        import torch.nn as nn
        from torch.utils.data import DataLoader, TensorDataset

        data = df[self.columns].to_numpy(dtype=np.float32)
        self.mean = data.mean(axis=0)
        self.std = np.clip(data.std(axis=0), 1e-6, None)
        normed = (data - self.mean) / self.std
        # tanh generator → clip to [-1, 1] after scaling by 3σ-ish
        scaled = np.clip(normed / 3.0, -1.0, 1.0).astype(np.float32)
        loader = DataLoader(
            TensorDataset(torch.from_numpy(scaled)),
            batch_size=min(batch_size, max(8, len(scaled))),
            shuffle=True,
            drop_last=False,
        )
        opt_g = torch.optim.Adam(self.G.parameters(), lr=2e-4, betas=(0.5, 0.9))
        opt_d = torch.optim.Adam(self.D.parameters(), lr=2e-4, betas=(0.5, 0.9))
        bce = nn.BCEWithLogitsLoss()
        self.G.train()
        self.D.train()
        for epoch in range(epochs):
            g_loss = d_loss = 0.0
            n_b = 0
            for (real,) in loader:
                real = real.to(self.device)
                bs = real.size(0)
                z = torch.randn(bs, LATENT_DIM, device=self.device)
                fake = self.G(z).detach()
                opt_d.zero_grad()
                loss_d = bce(self.D(real), torch.ones(bs, 1, device=self.device)) + bce(
                    self.D(fake), torch.zeros(bs, 1, device=self.device)
                )
                loss_d.backward()
                opt_d.step()
                z = torch.randn(bs, LATENT_DIM, device=self.device)
                opt_g.zero_grad()
                loss_g = bce(self.D(self.G(z)), torch.ones(bs, 1, device=self.device))
                loss_g.backward()
                opt_g.step()
                g_loss += float(loss_g.item())
                d_loss += float(loss_d.item())
                n_b += 1
            if (epoch + 1) % 10 == 0 or epoch == 0:
                print(f"TorchCTGAN epoch {epoch + 1}/{epochs} g={g_loss / max(n_b, 1):.4f} d={d_loss / max(n_b, 1):.4f}")
        self._fitted = True

    def sample(self, n_samples: int) -> pd.DataFrame:
        import torch

        self.G.eval()
        with torch.no_grad():
            z = torch.randn(n_samples, LATENT_DIM, device=self.device)
            fake = self.G(z).cpu().numpy() * 3.0 * self.std + self.mean
        out = pd.DataFrame(fake, columns=self.columns)
        if "Amount" in out.columns:
            out["Amount"] = np.clip(out["Amount"], 0.01, None)
        if "Time" in out.columns:
            out["Time"] = np.clip(out["Time"], 0.0, None)
        return out

    def save(self, path: Path) -> None:
        import torch

        torch.save(
            {
                "kind": "torch_ctgan",
                "columns": self.columns,
                "mean": self.mean,
                "std": self.std,
                "G": self.G.state_dict(),
            },
            path,
        )

    @classmethod
    def load(cls, path: Path) -> "TorchCTGAN":
        import torch

        blob = torch.load(path, map_location="cpu", weights_only=False)
        obj = cls(blob["columns"])
        obj.mean = blob["mean"]
        obj.std = blob["std"]
        obj.G.load_state_dict(blob["G"])
        obj._fitted = True
        return obj


class AttackGenerator:
    def __init__(self, fraud_samples: pd.DataFrame | None = None) -> None:
        self.fraud_samples = fraud_samples.copy() if fraud_samples is not None else None
        self.synthesizer = None
        self._fitted = False

    def train(self, epochs: int | None = None, fraud_samples: pd.DataFrame | None = None) -> None:
        if fraud_samples is not None:
            self.fraud_samples = fraud_samples.copy()
        if self.fraud_samples is None or self.fraud_samples.empty:
            raise ValueError("No fraud samples to fit CTGAN")

        fit_df = self._ctgan_frame(self.fraud_samples)
        epochs = epochs if epochs is not None else CTGAN_EPOCHS
        try:
            from sdv.metadata import SingleTableMetadata
            from sdv.single_table import CTGANSynthesizer

            metadata = SingleTableMetadata()
            metadata.detect_from_dataframe(fit_df)
            n = len(fit_df)
            batch_size = min(60, max(10, (n // 4) * 2))
            if batch_size % 2:
                batch_size += 1
            self.synthesizer = CTGANSynthesizer(
                metadata,
                epochs=epochs,
                batch_size=batch_size,
                verbose=True,
            )
            self.synthesizer.fit(fit_df)
            self._fitted = True
            return
        except Exception as exc:  # noqa: BLE001
            print(f"SDV CTGAN unavailable ({exc}); trying TVAE")

        try:
            from sdv.metadata import SingleTableMetadata
            from sdv.single_table import TVAESynthesizer

            metadata = SingleTableMetadata()
            metadata.detect_from_dataframe(fit_df)
            self.synthesizer = TVAESynthesizer(metadata, epochs=epochs, verbose=True)
            self.synthesizer.fit(fit_df)
            self._fitted = True
            return
        except Exception as exc:  # noqa: BLE001
            print(f"SDV TVAE unavailable ({exc}); training Torch GAN")

        try:
            gan = TorchCTGAN(list(fit_df.columns))
            gan.fit(fit_df, epochs=epochs)
            self.synthesizer = gan
            self._fitted = True
        except Exception as exc:  # noqa: BLE001
            print(f"Torch CTGAN fit failed ({exc}); bootstrap sampler will be used")
            self.synthesizer = None
            self._fitted = False

    def generate_synthetic_fraud(
        self,
        n_samples: int = 1000,
        family: str | None = None,
        rng: np.random.Generator | None = None,
    ) -> pd.DataFrame:
        rng = rng or np.random.default_rng(RANDOM_STATE)
        if self.synthesizer is not None and self._fitted:
            synthetic = self.synthesizer.sample(n_samples)
        else:
            synthetic = self._bootstrap(n_samples, rng)

        synthetic = synthetic.reset_index(drop=True)
        if family:
            synthetic = overlay_family(synthetic, family, rng, set_amount=False)
        synthetic["Class"] = 1
        synthetic["generation_method"] = self.method
        synthetic["attack_generation_method"] = (
            f"{self.method}+overlay:{family}" if family else f"{self.method}+overlay"
        )
        return synthetic

    def generate_mixed_families(
        self,
        n_samples: int,
        families: list[str],
        rng: np.random.Generator | None = None,
    ) -> pd.DataFrame:
        rng = rng or np.random.default_rng(RANDOM_STATE)
        chosen = rng.choice(families, size=n_samples)
        base = self.generate_synthetic_fraud(n_samples, family=None, rng=rng)
        parts = []
        for family in families:
            idx = np.where(chosen == family)[0]
            if len(idx) == 0:
                continue
            parts.append(overlay_family(base.iloc[idx], family, rng, set_amount=False))
        out = pd.concat(parts, axis=0).reset_index(drop=True)
        out["Class"] = 1
        out["generation_method"] = self.method
        out["attack_generation_method"] = f"{self.method}+overlay:mixed"
        return out

    def generate_from_legitimate(
        self,
        legit_df: pd.DataFrame,
        n_samples: int = 1,
        family: str = "prompt_injection_pay",
        intensity: str = "medium",
        rng: np.random.Generator | None = None,
    ) -> dict[str, Any]:
        """Legit seed → rule mutation → optional CTGAN PCA refine."""
        rng = rng or np.random.default_rng(RANDOM_STATE)
        if family not in FAMILY_TEMPLATES:
            raise ValueError(f"Family {family} is not generatable")
        if legit_df is None or len(legit_df) == 0:
            raise ValueError("No legitimate rows to mutate")
        n = max(1, int(n_samples))
        seed = legit_df.sample(n=min(n, len(legit_df)), replace=n > len(legit_df), random_state=int(rng.integers(0, 10_000)))
        seed = seed.reset_index(drop=True)
        before = overlay_legitimate(seed.copy(), rng)
        before["attack_family"] = "legitimate"
        mutated = overlay_family(seed.copy(), family, rng, set_amount=True, intensity=intensity)
        pca_cols = [c for c in PCA_FEATURES if c != "Amount" and c in mutated.columns]
        refine = "none"
        if self.synthesizer is not None and self._fitted:
            try:
                drawn = self.synthesizer.sample(len(mutated))
                for col in pca_cols:
                    if col in drawn.columns:
                        mutated[col] = drawn[col].to_numpy()[: len(mutated)]
                refine = self.method
            except Exception:  # noqa: BLE001
                refine = "none"
        mutated["Class"] = 1
        mutated["generation_method"] = f"rules+{refine if refine != 'none' else 'bootstrap'}"
        mutated["attack_generation_method"] = f"legit+overlay:{family}:{intensity}"
        preview_cols = [
            c
            for c in [
                "Amount",
                "device_new",
                "velocity_1h",
                "location_mismatch",
                "beneficiary_name_match",
                "mule_account_risk",
                "constraint_violation",
                "amount_vs_limit_ratio",
                "hour_of_day",
                "kyc_liveness_risk",
                "document_tamper_score",
                "biometric_mismatch",
                "voiceprint_mismatch",
            ]
            if c in mutated.columns
        ]
        before_row = {c: _json_num(before.iloc[0][c]) for c in preview_cols}
        after_row = {c: _json_num(mutated.iloc[0][c]) for c in preview_cols}
        changed = [c for c in preview_cols if before_row.get(c) != after_row.get(c)]
        contract = MUTATION_CONTRACTS.get(family) or MUTATION_CONTRACTS.get("adaptive") or {}
        return {
            "family": family,
            "intensity": intensity,
            "n": int(len(mutated)),
            "generation_method": mutated["generation_method"].iloc[0],
            "mutation_contract": contract,
            "before": before_row,
            "after": after_row,
            "changed_columns": changed,
            "unchanged_columns": [c for c in preview_cols if c not in changed],
            "transactions": mutated.to_dict(orient="records"),
            "seed_preview": before.to_dict(orient="records"),
        }

    def mutate_for_attack_vector(
        self,
        base_transaction: pd.Series | dict[str, Any],
        attack_type: str,
        intensity: str = "medium",
    ) -> pd.Series:
        """Rule mutation for a BUILD REQUEST vector id or catalog family id."""
        family = VECTOR_TO_FAMILY.get(attack_type, attack_type)
        if family not in FAMILY_TEMPLATES:
            raise ValueError(f"Family {family} is not generatable")
        row = pd.Series(base_transaction)
        mutated = overlay_family(pd.DataFrame([row]), family, set_amount=True, intensity=intensity)
        return mutated.iloc[0]

    @property
    def method(self) -> str:
        if not self._fitted or self.synthesizer is None:
            return "bootstrap"
        if isinstance(self.synthesizer, TorchCTGAN):
            return "torch_gan"
        name = type(self.synthesizer).__name__.lower()
        if "tvae" in name:
            return "tvae"
        if "ctgan" in name:
            return "ctgan"
        return "sdv"

    def evaluate_fidelity(self, synthetic: pd.DataFrame, real: pd.DataFrame) -> dict[str, Any]:
        ks_tests: dict[str, dict[str, float]] = {}
        wasserstein: dict[str, float] = {}
        cols = [c for c in ["Amount", "V1", "V14", "Time"] if c in synthetic.columns and c in real.columns]
        for col in cols:
            s = synthetic[col].dropna().to_numpy(dtype=float)
            r = real[col].dropna().to_numpy(dtype=float)
            if len(s) == 0 or len(r) == 0:
                continue
            ks_stat, p_value = stats.ks_2samp(s, r)
            ks_tests[col] = {"ks_statistic": float(ks_stat), "p_value": float(p_value)}
            scale = float(np.std(r) + 1e-6)
            wasserstein[col] = float(stats.wasserstein_distance(s, r) / scale)
        ks_vals = [v["ks_statistic"] for v in ks_tests.values()]
        mean_ks = float(np.mean(ks_vals)) if ks_vals else None
        mean_wd = float(np.mean(list(wasserstein.values()))) if wasserstein else None
        if mean_ks is None:
            grade = "unknown"
            afs = None
        elif mean_ks < 0.10:
            grade = "excellent"
            afs = (1.0 - mean_ks) * 100.0
        elif mean_ks < 0.20:
            grade = "good"
            afs = (1.0 - mean_ks) * 100.0
        else:
            grade = "weak"
            afs = (1.0 - mean_ks) * 100.0
        return {
            "ks_tests": ks_tests,
            "wasserstein": wasserstein,
            "mean_ks": mean_ks,
            "mean_wasserstein": mean_wd,
            "grade": grade,
            "attack_fidelity_score": round(afs, 1) if afs is not None else None,
            "simulator": self.simulator_match(synthetic),
            "tabular_method": self.method,
            "synthetic_shape": list(synthetic.shape),
            "real_shape": list(real.shape),
        }

    def simulator_match(self, synthetic: pd.DataFrame) -> dict[str, Any]:
        """Share of overlay values that sit inside the family template."""
        if "attack_family" not in synthetic.columns:
            return {"match_rate": None, "n": int(len(synthetic)), "by_family": {}}
        by_family: dict[str, float] = {}
        hits = 0
        n = 0
        for family, part in synthetic.groupby("attack_family"):
            tmpl = FAMILY_TEMPLATES.get(str(family))
            if not tmpl:
                continue
            ok = np.ones(len(part), dtype=bool)
            for key, spec in tmpl.items():
                if key == "amount_range" or key not in part.columns:
                    continue
                vals = part[key].to_numpy(dtype=float)
                if isinstance(spec, tuple) and len(spec) == 2:
                    ok &= (vals >= float(spec[0])) & (vals <= float(spec[1]))
                else:
                    ok &= np.isclose(vals, float(spec), atol=0.51)
            rate = float(ok.mean()) if len(part) else 0.0
            by_family[str(family)] = round(rate, 3)
            hits += int(ok.sum())
            n += int(len(part))
        return {
            "match_rate": round(hits / n, 3) if n else None,
            "n": n,
            "by_family": by_family,
        }

    def save(self, path: Path | None = None) -> Path:
        path = path or CTGAN_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(self.synthesizer, TorchCTGAN) and self._fitted:
            self.synthesizer.save(path)
        elif self.synthesizer is not None and self._fitted:
            self.synthesizer.save(str(path))
        else:
            path.write_text("bootstrap")
        return path

    @classmethod
    def load(cls, path: Path | None = None, fraud_samples: pd.DataFrame | None = None) -> "AttackGenerator":
        path = path or CTGAN_PATH
        gen = cls(fraud_samples=fraud_samples)
        if not path.exists() or path.stat().st_size < 20:
            return gen
        try:
            import torch

            blob = torch.load(path, map_location="cpu", weights_only=False)
            if isinstance(blob, dict) and blob.get("kind") == "torch_ctgan":
                gen.synthesizer = TorchCTGAN.load(path)
                gen._fitted = True
                return gen
        except Exception:  # noqa: BLE001
            pass
        try:
            from sdv.single_table import CTGANSynthesizer

            gen.synthesizer = CTGANSynthesizer.load(str(path))
            gen._fitted = True
            return gen
        except Exception:  # noqa: BLE001
            pass
        try:
            from sdv.single_table import TVAESynthesizer

            gen.synthesizer = TVAESynthesizer.load(str(path))
            gen._fitted = True
        except Exception:  # noqa: BLE001
            gen.synthesizer = None
            gen._fitted = False
        return gen

    def _ctgan_frame(self, df: pd.DataFrame) -> pd.DataFrame:
        cols = [c for c in CTGAN_COLUMNS if c in df.columns]
        return df[cols].astype(float).reset_index(drop=True)

    def _bootstrap(self, n_samples: int, rng: np.random.Generator) -> pd.DataFrame:
        if self.fraud_samples is None or self.fraud_samples.empty:
            raise RuntimeError("No fraud samples available for bootstrap generation")
        base = self._ctgan_frame(self.fraud_samples)
        idx = rng.integers(0, len(base), size=n_samples)
        out = base.iloc[idx].reset_index(drop=True).copy()
        vcols = [c for c in out.columns if c.startswith("V")]
        noise = rng.normal(0.0, 0.06, size=(n_samples, len(vcols)))
        out[vcols] = out[vcols].to_numpy() * (1.0 + noise)
        amt_noise = rng.normal(0.0, 0.04, size=n_samples)
        out["Amount"] = np.clip(out["Amount"].to_numpy() * (1.0 + amt_noise), 0.01, None)
        return out


__all__ = ["AttackGenerator"]
