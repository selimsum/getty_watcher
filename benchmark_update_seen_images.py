import time
import random

def baseline(seen_list, new_ids):
    seen = seen_list.copy()
    changed = False

    start = time.perf_counter()
    seen_set = set(seen)
    for img_id in new_ids:
        if img_id not in seen_set:
            seen.append(img_id)
            seen_set.add(img_id)
            changed = True
    end = time.perf_counter()
    return end - start

def optimized(seen_list, new_ids):
    seen = seen_list.copy()
    changed = False

    start = time.perf_counter()
    seen_set = set(seen)
    new_unique = [img_id for img_id in dict.fromkeys(new_ids) if img_id not in seen_set]
    if new_unique:
        seen.extend(new_unique)
        changed = True
    end = time.perf_counter()
    return end - start

def main():
    seen_list = [str(i) for i in range(10000)]
    new_ids = [str(random.randint(0, 20000)) for _ in range(5000)]

    baseline_time = baseline(seen_list, new_ids)
    optimized_time = optimized(seen_list, new_ids)

    print(f"Baseline:  {baseline_time:.6f} seconds")
    print(f"Optimized: {optimized_time:.6f} seconds")
    print(f"Improvement: {baseline_time / optimized_time:.2f}x faster")

if __name__ == "__main__":
    main()
