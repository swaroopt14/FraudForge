from app.evaluation.fidelity import fidelity_report
from app.simulation.legit import generate_legitimate


def test_attack_fidelity(controller, payments) -> None:
    legit = payments.loc[payments["fraud_label"] == 0]
    contract = controller.build_contract("SLOW-001", difficulty="HIGH", transaction_count=400, seed=3)
    atk = controller.generate(contract)
    synth = generate_legitimate(controller.profiles(), 400, seed=3)
    attack_fid = fidelity_report(legit.head(800), atk)
    legit_fid = fidelity_report(legit.head(800), synth)
    for key in ("amount_distribution", "time_distribution", "velocity_distribution", "merchant_distribution", "customer_behavior", "sequence_similarity", "beneficiary_behavior", "overall_fidelity"):
        assert 0.0 <= attack_fid[key] <= 1.0
    # HIGH low-and-slow should not wreck amount fidelity vs a legit draw
    assert attack_fid["amount_distribution"] >= min(0.45, legit_fid["amount_distribution"] - 0.25)
