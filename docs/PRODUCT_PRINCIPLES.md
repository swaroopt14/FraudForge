

1. This is an Adversarial Payment Defense Lab.

2. Red Team and Blue Team are separate subsystems.

3. AI reasoning generates attack specifications, not raw high-volume transactions.

4. Deterministic simulators generate high-volume synthetic transactions.

5. Synthetic data must preserve realistic payment distributions and behavioral relationships.

6. Network attacks must generate relationships, not only fraudulent rows.

7. Novel threats must pass validation before simulation.

8. Every simulation must be reproducible using a seed.

9. Every model result must be measurable.

10. No hardcoded benchmark numbers.

11. No data leakage.

12. Every phase has acceptance benchmarks.

13. Do not move to the next phase unless the current phase passes its benchmarks.

14. The Blue Team should sometimes fail naturally during stress testing.

15. Every Red/Blue loop generates an evaluation report.

16. Reports become structured feedback for the next iteration.

17. Never interact with real payment systems.

18. All attacks operate against synthetic/sandbox data.