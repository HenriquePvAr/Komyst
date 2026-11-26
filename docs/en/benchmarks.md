# Internal benchmarks

[Português](../benchmarks.md) · [Home](../../README.en.md)

Seven full-chapter runs on Windows during Beta development. The IDs below identify the published measurements. The chapters used in the tests are kept internally.

| Run | Date in 2026 | Source → PT-BR | Logical pages | Detected groups | Total (s) | Mean (s/page) |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| B01 | 2026-11-18 | KO | 93 | 232 | 411.64 | 4.43 |
| B02 | 2026-11-17 | EN | 65 | 91 | 342.64 | 5.27 |
| B03 | 2026-11-22 | RU | 57 | 219 | 425.27 | 7.46 |
| B04 | 2026-11-18 | EN | 21 | 84 | 162.18 | 7.72 |
| B05 | 2026-11-13 | EN | 85 | 234 | 793.11 | 9.33 |
| B06 | 2026-11-23 | EN | 42 | 310 | 439.34 | 10.46 |
| B07 | 2026-11-19 | EN | 31 | 223 | 368.13 | 11.88 |

## Method

- The mean is recorded elapsed time divided by processed logical pages. The pipeline can combine or split downloaded slices to form a logical page.
- The records show full processing, Fast Mode off, source collection without a download cache, cleanup, translation, typesetting and PDF. Dates use Manaus local time. Connection speed and latency were unmeasured.
- A separate reference run documented a Ryzen 5 5600GT, 32 GB of RAM and a Radeon RX 6600 with 8 GB. Exact hardware and app builds are unconfirmed per run. The reference setup is not a minimum requirement.
- Group counts represent detections. A coverage claim would require annotated ground truth. OCR and translation accuracy require textual and semantic checks. Cleanup and reconstruction require visual review. A PDF artifact alone does not certify the pages or replace review.

[Benchmarks on the official website](https://komyst.com.br/benchmarks.html).
