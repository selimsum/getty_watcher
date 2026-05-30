import time
import random

# Mock the data
seen_for_kw_list = [str(i) for i in range(10000)]
found_images = [{'id': str(random.randint(0, 20000)), 'date': '2023-01-01'} for _ in range(5000)]

def baseline():
    last_id = None
    cutoff_date = None
    new_images = []
    seen_for_kw = set(seen_for_kw_list)
    max_date_found = None

    start = time.perf_counter()
    for img in found_images:
        img_date = None

        if (last_id and img['id'] == last_id) or (img['id'] in seen_for_kw):
            continue

        new_images.append(img)
    end = time.perf_counter()
    return end - start

def optimized():
    last_id = None
    cutoff_date = None
    new_images = []
    seen_for_kw = set(seen_for_kw_list)
    max_date_found = None

    start = time.perf_counter()
    for img in found_images:
        img_date = None

        if (last_id and img['id'] == last_id) or (img['id'] in seen_for_kw):
            continue

        new_images.append(img)
    end = time.perf_counter()
    return end - start

baseline_time = baseline()
optimized_time = optimized()

print(f"Baseline:  {baseline_time:.6f} seconds")
print(f"Optimized: {optimized_time:.6f} seconds")
print(f"Improvement: {baseline_time / optimized_time:.2f}x faster")
