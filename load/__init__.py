"""
Frequency-domain FLS (fatigue limit state) module for the monopile concept
design engine.

Replaces engine._fls_check's single-equivalent-stress-range Palmgren-Miner
check with a spectral method (Kaimal wind + JONSWAP wave -> dynamic
amplification -> spectral moments -> Dirlik rainflow-equivalent damage),
opted into via DesignInputs.fls_method="spectral" -- see fls_spectral.py and
docs/method_update_log.md for the rollout/validation plan. Off by default
(fls_method="simple"); engine._fls_check is unchanged.

Scope (current): DLC12 (power production) only. DLC72 (parked/idling) is an
accepted label in DesignInputs.dlcs_to_run but not yet implemented -- see
fls_spectral.py. ULS/extreme DLCs (13/16/61) are out of scope entirely.

Depends on engine.py (imports several of its private helpers and constants,
the same pattern bc90/engine_bc90.py already uses) but engine.py does not
import this package at module load time -- see the deferred import inside
engine.evaluate_monopile, which avoids a circular import.
"""
