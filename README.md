# Car Scraper — generation-labelled image dataset builder

Builds a modern, **generation-labelled** car image dataset (a CompCars replacement that
fixes the year-vs-generation problem). Cars from different years but the same generation
share a label; different generations of a model are distinct. Trims are recorded in the
schema but ignored for classification.

## Pipeline

```
scraper.survey()  → candidates (make, model, year)         [no image download]
   ↓  resolve year → generation, bucket by generation + source group
   ↓  images_per_group = ceil(target / num_groups)          [balance + diversity]
scraper.fetch_images(candidate, max_n)                       [download up to quota]
   ↓  YOLO (biggest car) → full image + bbox label
DataSaver → Dataset/images|labels/Make/Model/Generation/
```

- **Schema / generations:** `maps/generations.json`, built from the autoevolution scrape
  (`../car-schemas/cars_dataset.json`) by `src/utils/populate_generations.py`.
  Generations are facelift-granular, non-overlapping year ranges.
- **Generation resolution:** `src/core/maps_manager.py` `resolve_generation(make, model, year)`.
- **Detector:** `src/utils/yolo_detector.py` (YOLOv8n, COCO class 2 = car, biggest box).
- **Output:** full image + YOLO label `make_id.model_id.gen_id x y w h` (normalized).
- **Balance:** per-generation `--target` (default 150), spread across source groups.

## Setup

```bash
pip install -r requirements.txt          # needs ultralytics>=8.3 for torch>=2.6
python -m src.utils.populate_generations  # (re)build maps/generations.json from new data
```

## Run

```bash
# Validated source (open API, works anywhere) — also the end-to-end test:
python main.py --site commons --models "Toyota:Camry,Toyota:Corolla,Honda:Accord" --target 150

# Listings source (run on your own machine, see note):
python main.py --site truecar --models "Toyota:Camry" --target 150

python main.py --list-sites
python -m src.utils.verify_pipeline       # fast offline smoke test (mocked YOLO)
```

`--test` clamps the target to 8 for a quick run. `--dataset` / `--maps` override paths.

## Sources & the bot-protection reality

| Source | Status |
|---|---|
| **Wikimedia Commons** (`commons`) | ✅ Works everywhere. Open API, license-clean, generation-categorised. Used to validate the pipeline and as a supplementary source. |
| **TrueCar** (`truecar`) | ✅ Working via `undetected-chromedriver` (`engine:"undetected"`). PerimeterX blocks plain Selenium by *fingerprint*, not IP — a normal residential IP needs **no proxy**. Page 1 loads reliably. For pagination, see the solve-once note below. |
| Cars.com / Autotrader / Edmunds / CarGurus | ❌ Blocked during testing (Cloudflare / reCAPTCHA / empty JS shells). The interface is site-agnostic, so adding one is just a new class in `src/scrapers/`. |

### TrueCar / PerimeterX notes (verified)

- The block is **automation fingerprinting, not your IP** — your normal browser opens TrueCar
  on the same IP, so a proxy doesn't help. `undetected-chromedriver` patches the fingerprint
  and gets straight through (no proxy, no datacenter).
- **Multiple images per listing:** a listing's photos share one timestamp and differ only by a
  3-digit index (`.../{VIN}/001_<ts>.jpg`, `002_…`, up to ~5). `fetch_images` probes the index
  until a gap, so rich listings give up to `max_images_per_listing` (5) and sparse/sponsored
  ones give 1. Images are upscaled to `image_width` (1280px). The balancer takes
  `ceil(target / num_listings)` per listing (capped at 5), so the target is spread across many
  cars first, then deepened per listing only when listings are scarce.
- **Pagination:** a direct jump to `?page=2+` can trigger a fresh PerimeterX challenge. With
  `"user_data_dir": ".tc_profile"` (default) and `headless:false`, run once, **solve the
  press-and-hold challenge in the visible window**; the clearance cookie persists in the
  profile and later pages/runs work. Page 1 alone yields ~30 listings/model with no challenge;
  reaching 100–150/generation needs the multi-page (solved-profile) run.
- Only set `"proxy"` for high-volume scraping (rotating **residential**, not datacenter) or a
  flagged IP. Set `"chrome_version"` only if auto-detect fails.

Adding a site = implement `survey()` and `fetch_images()` from `src/scrapers/base.py` and
register it in `main.py`’s `SCRAPERS` dict.

## GPU machine notes

- YOLO auto-uses CUDA when available (ultralytics); no code change needed.
- `Dataset/` resumes naturally: `is_full` counts existing images per generation, so re-runs
  top up toward `--target` without duplicating finished generations.

## Known limitations / next steps

- **Generation boundaries** are auto-derived and ±1 year in places (autoevolution’s inclusive
  year convention). `maps/generations.json` is human-editable; curate the publication subset.
- **Coverage:** ~46/82 legacy makes matched autoevolution; Chinese-brand models in CompCars
  need another schema source.
- Years with no matching generation fall back to the raw year as the label
  (e.g. a 1984 Corolla → folder `1984`).
