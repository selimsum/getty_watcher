import time
import random

def baseline_mark_image_seen(data, keyword, image_id):
    seen = data.setdefault("seen_images", {}).setdefault(keyword, [])
    if image_id not in seen:
        seen.append(image_id)

def optimized_mark_image_seen(data, seen_sets, keyword, image_id):
    seen = data.setdefault("seen_images", {}).setdefault(keyword, [])
    if keyword not in seen_sets:
        seen_sets[keyword] = set(seen)
    seen_set = seen_sets[keyword]

    if image_id not in seen_set:
        seen.append(image_id)
        seen_set.add(image_id)

def main():
    # Setup data
    data_baseline = {"seen_images": {"test": [str(i) for i in range(10000)]}}
    new_ids = [str(random.randint(0, 20000)) for _ in range(5000)]

    start = time.perf_counter()
    for img_id in new_ids:
        baseline_mark_image_seen(data_baseline, "test", img_id)
    baseline_time = time.perf_counter() - start

    data_optimized = {"seen_images": {"test": [str(i) for i in range(10000)]}}
    seen_sets = {"test": set(data_optimized["seen_images"]["test"])}

    start = time.perf_counter()
    for img_id in new_ids:
        optimized_mark_image_seen(data_optimized, seen_sets, "test", img_id)
    optimized_time = time.perf_counter() - start

    print(f"Baseline:  {baseline_time:.6f} seconds")
    print(f"Optimized: {optimized_time:.6f} seconds")
    print(f"Improvement: {baseline_time / optimized_time:.2f}x faster")

if __name__ == "__main__":
    main()
