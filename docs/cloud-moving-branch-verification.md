# SharkByte moving-branch certification: Colab and GCE reproduction

**Baseline revision:** `7793d5eace34456ce1cc57f85f4d75cf84c8e889` (PR #22 merge). This procedure uses the existing audited `tools/high_support/check_moving_branch_protection.py`; it does not add a new numerical engine. No new Google Cloud or Colab run is claimed until an actual source-bound receipt is produced.

## One-click Google Colab

[Open the notebook](https://colab.research.google.com/github/reggaesharkk/SharkByte/blob/main/notebooks/SharkByte-Colab-Moving-Branch-Certification.ipynb). Select a CPU runtime, then **Runtime → Run all**. The notebook clones a pinned source, probes available RAM and cgroup headroom, runs the original mapping/replay harness inside an externally time-limited child process, and exports a ZIP containing the JSON evidence and manifest. PASS requires matching source hashes, the 444 single-gate mappings, 322,560 four-qubit affine maps, 5,160,960 images, valid exact rational inequalities and expected decisions. A failed or refused run must not be described as PASS.

Colab free RAM is not guaranteed to be 32 GiB. The child receives the smaller of 24 GiB address-space allowance or 65% of currently available memory. This is **not** a hard resident-memory cap. The parent's 30-minute timeout kills the worker process group; the Colab service itself may terminate earlier.

## Google Compute Engine 32-GiB host — manual execution only

Use an `e2-standard-8` Ubuntu VM (8 vCPUs, 32 GiB RAM), subject to current region quota and trial eligibility. This instance is not an always-free tier VM. Check the live price, credit eligibility and billing alerts before creation. **Budget alerts are not spending caps.** Stop or delete the VM after retrieving receipts; stopped boot disks can keep costing money.

Example using `gcloud` (nothing below has been executed by this documentation):

```bash
PROJECT_ID="YOUR_PROJECT_ID"
ZONE="us-central1-a"
VM="sharkbyte-moving-32g"
gcloud config set project "$PROJECT_ID"
gcloud compute instances create "$VM" --zone "$ZONE" --machine-type=e2-standard-8 \
  --image-family=ubuntu-2404-lts-amd64 --image-project=ubuntu-os-cloud \
  --boot-disk-size=40GB --boot-disk-type=pd-balanced \
  --max-run-duration=2h --instance-termination-action=STOP
gcloud compute ssh "$VM" --zone "$ZONE"
```

Inside the VM:

```bash
sudo apt-get update && sudo apt-get install -y git python3
git clone https://github.com/reggaesharkk/SharkByte.git
cd SharkByte
git checkout --detach 7793d5eace34456ce1cc57f85f4d75cf84c8e889
mkdir -p "$HOME/sharkbyte-evidence"
# Limit child virtual address space to 24 GiB; refuse if the OS has less headroom.
python3 - <<'PY'
import os, resource, subprocess, hashlib, json, pathlib, time
from fractions import Fraction
repo=pathlib.Path.cwd()
out=pathlib.Path.home()/"sharkbyte-evidence"
out.mkdir(exist_ok=True)
limit=24*1024**3
started=time.monotonic()
def prep():
    resource.setrlimit(resource.RLIMIT_AS,(limit,limit))
with (out/"staging.json").open("wb") as fp:
    proc=subprocess.run(["timeout","--signal=TERM","--kill-after=15s","1800s","python3","-B",
        "tools/high_support/check_moving_branch_protection.py"],stdout=fp,cwd=repo,preexec_fn=prep)
if proc.returncode:
    print("REFUSED/TIMEOUT:",proc.returncode);raise SystemExit(1)
record=json.loads((out/"staging.json").read_bytes())
assert record["implementation_commit"] == "7793d5eace34456ce1cc57f85f4d75cf84c8e889"
assert record["exhaustive_composed_affine_mappings"][-1]["affine_coordinate_maps"]==322560
assert record["exhaustive_composed_affine_mappings"][-1]["basis_images_checked"]==5160960
for path,h in record["source_hashes"].items():
    assert hashlib.sha256((repo/path).read_bytes()).hexdigest()==h,path
for case in record["randomized_signed_permutation_circuits"]:
    assert Fraction(case["exact_squared_error"])<=Fraction(case["certified_l2_bound"])**2
final=out/"gce-moving-cloud.json"
(out/"staging.json").replace(final)
manifest={"status":"PASS","source_commit":record["implementation_commit"],
    "elapsed_seconds":time.monotonic()-started,
    "receipt_bytes":final.stat().st_size,
    "sha256":hashlib.sha256(final.read_bytes()).hexdigest(),
    "worker_rlimit_as_bytes":limit}
(out/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(manifest)
PY
```

Use `gcloud compute scp --recurse` to retrieve the evidence directory and inspect it. Then **stop the instance**, or delete the VM and disk if no longer needed. The 2-hour automatic stop is a cost safety backstop. This worker cap is `RLIMIT_AS` (virtual address space); enforce a cgroup limit if hard RSS containment is needed.

## Claim boundaries

- Only **`x`, `z`, `cx`** signed basis permutations support this exact moving-coordinate guarantee; Hadamard, rotations and controlled phase are outside the certificate.
- The 322,560 affine maps are **coordinate transformations** on four-qubit computational-basis indices, not 322,560 independently simulated quantum algorithms.
- A 32-GiB host is the VM capacity, not the memory used by SharkByte. This benchmark is intentionally sparse and its run does not demonstrate dense 40- or 50-qubit simulation.
- Colab and GCE x86_64 do not replace native Windows ARM64 containment evidence. Success is source/host/workload-specific; retain REFUSED and TIMEOUT records.
- Existing one-click 16M, connected 32M and 4.29B historical notebooks remain unchanged.

References: [Colab resource FAQ](https://research.google.com/colaboratory/faq.html), [E2 VM types](https://docs.cloud.google.com/compute/docs/general-purpose-machines), [VM runtime limits](https://docs.cloud.google.com/compute/docs/instances/limit-vm-runtime), [Cloud budgets](https://docs.cloud.google.com/billing/docs/how-to/budgets).
