import csv
import subprocess
import time

import psutil

DIRS = ["CTD", "plus_CTD_BGC", "plus_DRIFTER", "plus_ARGO", "plus_UNDERWAY"]
RESULTS_FILE = "performance_results_fromdata.csv"

# Write header once at the start
with open(RESULTS_FILE, "w", newline="") as csvfile:
    writer = csv.writer(csvfile)
    writer.writerow(["Directory", "Time (s)", "Peak RAM (MB)"])


def run_and_trace(cmd):
    start_time = time.time()
    process = subprocess.Popen(cmd, shell=True)
    proc = psutil.Process(process.pid)
    peak_mem = 0

    while process.poll() is None:
        try:
            mem = proc.memory_info().rss / (1024 * 1024)  # MB
            if mem > peak_mem:
                peak_mem = mem
        except psutil.NoSuchProcess:
            break
        time.sleep(0.1)

    end_time = time.time()
    return end_time - start_time, peak_mem


for dir_name in DIRS:
    cmd = f"virtualship run ../{dir_name} --from-data ../data"
    print(f"Running: {cmd}")
    elapsed, peak_mem = run_and_trace(cmd)
    # Write result after each iteration
    with open(RESULTS_FILE, "a", newline="") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([dir_name, f"{elapsed:.2f}", f"{peak_mem:.2f}"])

print(f"\nResults written to {RESULTS_FILE}")
