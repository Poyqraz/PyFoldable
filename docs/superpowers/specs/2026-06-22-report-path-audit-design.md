# Report Path Audit — Design Spec

**Date:** 2026-06-22  
**Scope:** PyFoldable README “Ekler” tables and linked report assets  
**Constraint:** No physics model, CSV values, or test expectation changes.

## Problem

README Türkçe/İngilizce ek tabloları ile `figure_index.md` arasında tutarsızlık:
`diag_bias10_*.png` yolları dokümante edilmiş ancak hiçbir örnek betik bu dosyaları üretmiyor.

## Decision (Approach 1 — approved)

1. `diag_bias10_*` girişlerini `FIGURE_CATALOG`, `figure_index.md` ve rapor özet metninden kaldır.
2. README’de `report_key_results.csv` tam yola çek.
3. `reports/foldable_v2_engineering_design/README.md` içine görsel üretim notu ekle.
4. Rapor-üretim kodu (`engineering_design_report.py`) ile committed `figure_index.md` senkronize et.

## Out of scope

- Yeni PNG üretim pipeline’ı (bias10 şekilleri).
- `docx/` / `pdf/` teslim dosyalarının eklenmesi.
- Fizik, CSV sayıları, test assertion değişiklikleri.

## Verification

- `pytest tests/ -q` geçmeli.
- README tablolarındaki tüm yollar repo’da mevcut veya bilinçli placeholder (`docx/`, `pdf/`, `figures/`).
- `run_prescribed_rpm_physics.py` → `constant_7100_*.png` yolları `figure_index` ile uyumlu.
