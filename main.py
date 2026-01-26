import argparse
from src.core.maps_manager import MapsManager
from src.core.config_loader import ConfigLoader
from src.core.pipeline import Pipeline
# Import specific scrapers here or dynamically load
# from src.scrapers.site_a import SiteAScraper 

def main():
    parser = argparse.ArgumentParser(description="Car Scraper Pipeline")
    parser.add_argument("--site", type=str, help="Name of the site config to run")
    parser.add_argument("--list-sites", action="store_true", help="List available configs")
    args = parser.parse_args()
    
    config_loader = ConfigLoader()
    
    if args.list_sites:
        print("Available configs:", config_loader.list_configs())
        return

    maps_manager = MapsManager()
    pipeline = Pipeline(config_loader, maps_manager)
    
    # Logic to load the correct scraper class
    # For now, since we don't have concrete scrapers, we will just print message
    if args.site:
        print(f"Initializing scraper for {args.site}...")
        try:
            config = config_loader.load_config(args.site)
            # Here we would instantiate the scraper based on the config or a registry
            # scraper = ScraperRegistry.get(args.site)(config)
            # pipeline.process_scraper(scraper)
            print("Scraper not yet implemented. Please create a scraper class in src/scrapers/")
        except Exception as e:
            print(f"Error: {e}")
    else:
        print("Please provide --site")

if __name__ == "__main__":
    main()
