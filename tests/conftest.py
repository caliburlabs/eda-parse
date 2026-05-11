from __future__ import annotations

from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def liberty_asap7_ff() -> Path:
    return FIXTURES / "liberty" / "asap7_small_ff.lib.gz"


@pytest.fixture
def liberty_asap7_ss() -> Path:
    return FIXTURES / "liberty" / "asap7_small_ss.lib.gz"


@pytest.fixture
def liberty_sky130() -> Path:
    return FIXTURES / "liberty" / "sky130hd_tt.lib.gz"


@pytest.fixture
def lef_sky130_tech() -> Path:
    return FIXTURES / "lef" / "sky130_fd_sc_hd.tlef"


@pytest.fixture
def lef_sky130_merged() -> Path:
    return FIXTURES / "lef" / "sky130_fd_sc_hd_merged.lef"
