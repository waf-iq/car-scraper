import math
import time
from collections import defaultdict

import cv2
import numpy as np

from src.utils.yolo_detector import YoloDetector
from src.core.data_saver import DataSaver


class Pipeline:
    """
    Two-phase, balanced image-collection pipeline.

      Phase 1 (survey): ask the scraper for lightweight Candidate metadata (no image
        downloads), bucket candidates by generation and by source group (a listing /
        a category). For each generation compute
            images_per_group = ceil(target / num_groups)
        so the target is spread across as many distinct cars as possible.

      Phase 2 (capture): for each candidate, skip if its generation is already full,
        otherwise download up to its group's quota of images, run YOLO, and save the
        full image + bbox label.
    """

    def __init__(self, config_loader, maps_manager, target=150, dataset_dir="Dataset"):
        self.config_loader = config_loader
        self.maps_manager = maps_manager
        self.target = target
        self.detector = YoloDetector()
        self.saver = DataSaver(dataset_dir, maps_manager, target=target)

    def _gen_of(self, c):
        return self.maps_manager.resolve_generation(c.make, c.model, c.year)

    def process_scraper(self, scraper, targets):
        # ---- Phase 1: survey -------------------------------------------------
        print(f"[survey] collecting candidates for {targets} ...")
        candidates = list(scraper.survey(targets))
        # bucket: gen_key -> set(group_id); keep candidate order
        groups_per_gen = defaultdict(set)
        for c in candidates:
            gen = self._gen_of(c)
            groups_per_gen[(c.make, c.model, gen)].add(c.group_id)

        quota = {}
        print(f"[survey] {len(candidates)} candidates across {len(groups_per_gen)} generations:")
        for key, groups in sorted(groups_per_gen.items()):
            ng = len(groups)
            q = max(1, math.ceil(self.target / ng))
            quota[key] = q
            print(f"   {key[0]} {key[1]} {key[2]}: {ng} groups -> {q} img/group (target {self.target})")

        # ---- Phase 2: capture ------------------------------------------------
        saved = defaultdict(int)
        processed = 0
        for c in candidates:
            gen = self._gen_of(c)
            key = (c.make, c.model, gen)
            if self.saver.is_full(c.make, c.model, gen):
                continue
            q = quota.get(key, 1)
            for img_bytes in scraper.fetch_images(c, max_n=q):
                processed += 1
                arr = self._decode(img_bytes)
                if arr is None:
                    continue
                img, bbox, conf = self.detector.detect(arr)
                if not bbox:
                    print(f"  no car: {c.make} {c.model} {c.year}")
                    continue
                ip, _ = self.saver.save(img, bbox, c.make, c.model, gen)
                saved[key] += 1
                print(f"  saved {c.make} {c.model} {gen} ({conf:.2f}) -> {ip}")
                if self.saver.is_full(c.make, c.model, gen):
                    break

        print("\n[done] saved per generation:")
        for key, n in sorted(saved.items()):
            print(f"   {key[0]} {key[1]} {key[2]}: {n}")
        print(f"[done] processed {processed} images, saved {sum(saved.values())} total.")
        try:
            scraper.close()
        except Exception:
            pass

    @staticmethod
    def _decode(image_source):
        if isinstance(image_source, (bytes, bytearray)):
            arr = cv2.imdecode(np.frombuffer(image_source, np.uint8), cv2.IMREAD_COLOR)
            return arr
        if isinstance(image_source, np.ndarray):
            return image_source
        if isinstance(image_source, str):
            return cv2.imread(image_source)
        return None
