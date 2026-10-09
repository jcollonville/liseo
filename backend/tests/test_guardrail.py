import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "check_drm_guardrail.py"


def _load():
    spec = importlib.util.spec_from_file_location("liseo_guardrail", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_clean_tree_passes(tmp_path):
    guardrail = _load()
    (tmp_path / "adept_activate").write_bytes(b"activate only\n")
    assert guardrail.scan_tree(tmp_path) == []


def test_forbidden_filename_fails(tmp_path):
    guardrail = _load()
    (tmp_path / "adept_remove").write_bytes(b"")
    hits = guardrail.scan_tree(tmp_path)
    assert hits


def test_forbidden_feature_string_fails(tmp_path):
    guardrail = _load()
    (tmp_path / "downloader").write_bytes(b"usage: --export-private-key\n")
    hits = guardrail.scan_tree(tmp_path)
    assert any("export-private-key" in hit for hit in hits)


def test_patch_removes_drm_features():
    patch = (ROOT / "patches" / "libgourou-no-drm-removal.patch").read_text(encoding="utf-8")
    assert "utils/adept_remove.cpp" in patch
    assert "\n-TARGET_BINARIES=acsmdownloader adept_activate adept_remove adept_loan_mgt\n" in patch
    assert "export-private-key" in patch
    assert "--anonymous" in patch
    assert "-void DRMProcessor::removeDRM" in patch or "\n-    void DRMProcessor::removeDRM" in patch
