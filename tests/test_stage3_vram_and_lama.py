"""Stage 3: LaMa max-side downscale/upscale + DirectML fixed buckets, FLUX VRAM unload, PDH VRAM monitor, and ROI change metrics."""
from unittest import mock

import numpy as np

from komyst.clean.inpainting import advanced_art_inpainting as aai
from komyst.clean.inpainting import flux_edit
from komyst.config import settings as config
from komyst.ocr import ocr_balloon as ob
from komyst.runtime import resource_monitor as rm


def test_dml_bucket_selection_caps_distinct_shapes():
    assert aai._next_dml_bucket(120) == 256
    assert aai._next_dml_bucket(256) == 256
    assert aai._next_dml_bucket(257) == 384
    assert aai._next_dml_bucket(600) == 640
    assert aai._next_dml_bucket(896) == 896
    assert aai._next_dml_bucket(900) == 960


def test_lama_reconstruct_downscales_to_max_side_and_preserves_unmasked_pixels(monkeypatch):
    inpainter = aai.AdvancedArtInpainter(device="cpu")
    seen_shapes: list[tuple[int, int]] = []

    def fake_gpu_session(image_np, mask_np):
        seen_shapes.append(tuple(image_np.shape[2:]))
        # Return smooth midtone prediction of identical spatial shape (1, 3, H, W).
        return np.full_like(image_np, 0.72, dtype=np.float32)

    inpainter._gpu_session = fake_gpu_session
    inpainter._model = fake_gpu_session
    monkeypatch.setattr(inpainter, "verify_integrity", lambda: "a" * 64)
    monkeypatch.setattr(config, "LAMA_MAX_INFER_SIDE", 896)

    rng = np.random.default_rng(19)
    image = rng.integers(30, 220, size=(1500, 1700, 3), dtype=np.uint8)
    mask = np.zeros((1500, 1700), dtype=np.uint8)
    mask[300:1150, 350:1350] = 255

    composited, telemetry = inpainter.reconstruct(image, mask)
    assert len(seen_shapes) == 1
    assert seen_shapes[0][0] <= 896 and seen_shapes[0][1] <= 896
    assert seen_shapes[0][0] in aai._LAMA_DML_BUCKETS
    assert seen_shapes[0][1] in aai._LAMA_DML_BUCKETS
    assert telemetry["downscaled"] is True
    assert max(telemetry["infer_hw"]) == 896
    # Zero pixels outside mask may ever change.
    assert np.array_equal(composited[mask == 0], image[mask == 0])
    assert not np.array_equal(composited[mask > 0], image[mask > 0])


def test_flux_releases_directml_lama_before_launching_subprocess(tmp_path, monkeypatch):
    for name in ("sd-cli.exe", "flux-2-klein-4b-Q4_0.gguf", "flux2-vae.safetensors", "qwen3-4b-q4_k_m.gguf"):
        (tmp_path / name).write_bytes(b"stub")

    fake_inpainter = mock.MagicMock()
    fake_inpainter._gpu_session = object()
    fake_inpainter._model = fake_inpainter._gpu_session

    call_order: list[str] = []
    fake_inpainter.unload.side_effect = lambda: call_order.append("unload")

    def fake_run_reference_edit(source, *args, **kwargs):
        call_order.append("flux_subprocess")
        return source.copy()

    flux_edit.reset_call_budget()
    flux_edit._EDIT_CACHE.clear()
    monkeypatch.setattr(config, "GENERATIVE_INPAINT_ENABLED", True)
    monkeypatch.setattr(config, "GENERATIVE_INPAINT_MODEL_DIR", str(tmp_path))
    monkeypatch.setattr(aai, "get_default_inpainter", lambda: fake_inpainter)
    monkeypatch.setattr(flux_edit, "_run_reference_edit", fake_run_reference_edit)

    crop = np.full((128, 128, 3), 180, dtype=np.uint8)
    telemetry: dict = {}
    edited = flux_edit.flux_reference_edit(crop, prompt="restore", telemetry=telemetry)
    assert edited is not None
    assert call_order == ["unload", "flux_subprocess"]
    assert telemetry.get("directml_unloaded_before_flux") is True


def test_resource_monitor_records_gpu_vram_summary(tmp_path):
    monitor = rm.ResourceMonitor(tmp_path, enabled=True, interval_seconds=5.0, total_pages=4)
    if not monitor.enabled:
        return
    fake_vram = mock.MagicMock()
    fake_vram.sample_mb.side_effect = [2100.5, 3450.25]
    monitor._gpu_vram = fake_vram
    monitor._started = 1.0
    monitor._sample_once()
    monitor._sample_once()
    report = monitor.write_reports()
    assert report["gpu_vram_used_mb_peak"] == 3450.25
    assert report["gpu_vram_used_mb_avg"] == 2775.375


def test_roi_inpaint_change_metrics_exact_inside_and_outside_parity():
    before = np.full((1200, 1000, 3), 210, dtype=np.uint8)
    after = before.copy()
    mask = np.zeros((1200, 1000), dtype=np.uint8)
    mask[300:420, 250:450] = 255
    after[310:390, 260:430] = 240
    # Case 1: changes strictly within ROI (some inside mask, a small leak near mask inside ROI).
    after[299, 260:270] = 100
    m1 = ob._inpaint_change_metrics(before, after, mask)
    assert m1["changed_pixels_in_mask"] == 80 * 170
    assert m1["changed_pixels_outside_mask"] == 10

    # Case 2: rogue change far outside ROI triggers full-page fallback and still counts accurately.
    after_far = after.copy()
    after_far[50, 50:55] = 10
    m2 = ob._inpaint_change_metrics(before, after_far, mask)
    assert m2["changed_pixels_in_mask"] == 80 * 170
    assert m2["changed_pixels_outside_mask"] == 15
