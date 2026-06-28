import argparse

from src.core.maps_manager import MapsManager
from src.core.config_loader import ConfigLoader
from src.core.pipeline import Pipeline
from src.scrapers.commons import CommonsScraper
from src.scrapers.truecar import TrueCarScraper

SCRAPERS = {
    "commons": CommonsScraper,
    "truecar": TrueCarScraper,
}


def parse_models(s):
    """'Toyota:Camry,Toyota:Corolla' -> [('Toyota','Camry'),('Toyota','Corolla')]"""
    out = []
    for part in (s or "").split(","):
        part = part.strip()
        if not part:
            continue
        make, _, model = part.partition(":")
        if make and model:
            out.append((make.strip(), model.strip()))
    return out


def main():
    parser = argparse.ArgumentParser(description="Car listings image scraper")
    parser.add_argument("--site", choices=list(SCRAPERS), help="Scraper to run")
    parser.add_argument("--models", type=str, help="Make:Model[,Make:Model...] to collect")
    parser.add_argument("--target", type=int, default=150, help="Images per generation")
    parser.add_argument("--dataset", type=str, default="Dataset", help="Output dataset dir")
    parser.add_argument("--maps", type=str, default="maps", help="Maps dir")
    parser.add_argument("--list-sites", action="store_true")
    parser.add_argument("--test", action="store_true", help="Tight caps for a smoke test")
    args = parser.parse_args()

    if args.list_sites:
        print("Available scrapers:", list(SCRAPERS))
        return
    if not args.site or not args.models:
        print("Usage: python main.py --site commons --models 'Toyota:Camry,Honda:Accord' [--target N] [--test]")
        return

    targets = parse_models(args.models)
    if not targets:
        print("No valid --models parsed. Use Make:Model,Make:Model")
        return

    if args.test:
        args.target = min(args.target, 8)

    config_loader = ConfigLoader()
    try:
        config = config_loader.load_config(args.site)
    except FileNotFoundError:
        config = {}

    maps_manager = MapsManager(args.maps)
    pipeline = Pipeline(config_loader, maps_manager, target=args.target, dataset_dir=args.dataset)

    scraper = SCRAPERS[args.site](config)
    print(f"Running {args.site} for {targets} (target {args.target}/generation)")
    pipeline.process_scraper(scraper, targets)


if __name__ == "__main__":
    main()
