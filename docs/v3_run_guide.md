# Classifier v3: how to run it (PowerShell)

Close the SecureRAG app first so the GPU is free. Run every command from `E:\SecureRAG`
with the virtual environment active:

```powershell
cd E:\SecureRAG
.\.venv\Scripts\Activate.ps1
```

## Step 1. Create the locked test set (once, about 2 minutes)

Downloads deepset/prompt-injections and removes anything already in any training data.

```powershell
python scripts\v3\fetch_locked_test.py
```

## Step 2. Build the balanced training pool (about 2 minutes)

```powershell
python scripts\v3\build_training_pool_v3.py
```

It writes `data\processed_v3\` and never touches `data\processed\`.

## Step 3. Score the current FINAL model on the dev sets (about 5 minutes)

```powershell
python scripts\v3\score_v3.py --model models\securerag-classifier-FINAL --name FINAL --sets dev
```

## Step 4. Smoke test (about 1 minute)

```powershell
python scripts\v3\train_deberta_v3.py --seed 1 --smoke-test
```

It should end with `*** SMOKE TEST PASSED ***`.

## Step 5. Train three seeds (roughly 45–60 minutes each)

```powershell
foreach ($s in 1,2,3) { python scripts\v3\train_deberta_v3.py --seed $s }
```

Each run saves to `models\candidates\v3\seed1`, `seed2` and `seed3`. FINAL is never touched.

## Step 6. Score the three candidates (about 5 minutes each)

```powershell
foreach ($s in 1,2,3) { python scripts\v3\score_v3.py --model models\candidates\v3\seed$s --name v3-seed$s --sets dev }
```

## Step 7. Apply the pre-registered rule

```powershell
python scripts\v3\analyze_v3.py
```

This prints ACCEPT or REJECT and writes `docs\v3_dev_report.json`. Stop here and share the result.

## Step 8. Locked test, once (only after the decision)

Replace `seedN` with the deploy seed printed in step 7.

```powershell
python scripts\v3\score_v3.py --model models\securerag-classifier-FINAL --name FINAL --sets locked --unlock-locked-test
python scripts\v3\score_v3.py --model models\candidates\v3\seedN --name v3-seedN --sets locked --unlock-locked-test
python scripts\v3\analyze_v3.py --locked
```

Each locked run is recorded in `data\locked_test\ACCESS_LOG.jsonl`.

## If something fails

- Copy the last 20 lines of the error and share them. Do not edit the decision rule.
- A NaN warning that skips a batch is expected occasionally; many skips are not.
- To retry a seed, delete its candidate folder or pass a new `--run-tag`.
