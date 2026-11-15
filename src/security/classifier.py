from contextlib import nullcontext
import json
import math
from pathlib import Path

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


from src.utils.app_paths import FINAL_MODEL
from src.utils.operations import checkpoint


class SecurityCheckError(RuntimeError):
    """An unavailable/invalid score must never become a SAFE decision."""


def validated_score(value):
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise SecurityCheckError("Security check failed: invalid classifier score. Request stopped.")
    return value

class InjectionClassifier:
    def __init__(
        self,
        model_dir: Path = FINAL_MODEL,
        device: str | None = None,
        threshold: float | None = None,
    ):
        model_dir = Path(model_dir)
        config = json.loads(
            (model_dir / "classifier_config.json").read_text(encoding="utf-8")
        )

        self.threshold = float(config["threshold"] if threshold is None else threshold)
        validated_score(self.threshold)
        self.max_length = int(config["max_length"])
        self.device = torch.device(
            device or ("cuda" if torch.cuda.is_available() else "cpu")
        )

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_dir,
            local_files_only=True,
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            model_dir,
            local_files_only=True,
        ).to(self.device)
        self.model.eval()

        if self.tokenizer.cls_token_id is None:
            raise ValueError("Tokenizer has no CLS token")
        if self.tokenizer.sep_token_id is None:
            raise ValueError("Tokenizer has no SEP token")

        special_tokens = self.tokenizer.num_special_tokens_to_add(pair=False)
        self.window_size = self.max_length - special_tokens
        self.overlap = 64

        if self.window_size <= self.overlap:
            raise ValueError("Classifier window is too small")

    def _windows(self, text: str) -> list[dict]:
        ids = self.tokenizer.encode(text, add_special_tokens=False)
        if not ids:
            return []

        windows = []
        start = 0

        while start < len(ids):
            part = ids[start : start + self.window_size]

            input_ids = [
                self.tokenizer.cls_token_id,
                *part,
                self.tokenizer.sep_token_id,
            ]
            windows.append(
                {
                    "input_ids": input_ids,
                    "attention_mask": [1] * len(input_ids),
                }
            )

            if start + self.window_size >= len(ids):
                break

            start += self.window_size - self.overlap

        return windows

    @torch.inference_mode()
    def score(self, texts: list[str]) -> list[float]:
        results = []

        for text in texts:
            checkpoint()
            windows = self._windows(text)

            if not windows:
                results.append(0.0)
                continue

            highest_score = 0.0

            for start in range(0, len(windows), 16):
                checkpoint()
                batch = self.tokenizer.pad(
                    windows[start : start + 16],
                    padding=True,
                    return_tensors="pt",
                ).to(self.device)

                precision = (
                    torch.autocast("cuda", dtype=torch.bfloat16)
                    if self.device.type == "cuda"
                    else nullcontext()
                )

                with precision:
                    logits = self.model(**batch).logits.float()

                if logits.ndim != 2 or logits.shape[1] != 2 or not torch.isfinite(logits).all():
                    raise SecurityCheckError("Security check failed: invalid model output. Request stopped.")
                probabilities = torch.softmax(logits, dim=-1)[:, 1]
                highest_score = max(
                    highest_score,
                    validated_score(probabilities.max().item()),
                )

            results.append(highest_score)

        return results

    def classify(self, text: str) -> dict:
        score = self.score([text])[0]
        return {
            "label": "MALICIOUS" if score >= self.threshold else "SAFE",
            "score": score,
        }
