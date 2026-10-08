from __future__ import annotations

import argparse
import getpass
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from promptsmith.api import PROTOCOL_ID, ApiConfig, ChatCompletionsClient
from promptsmith.m1 import M1Assets
from promptsmith.session import SessionState
from promptsmith.workflow import M1CallFailure, Phase12Workflow


CASES = (
    "01_报名网站",
    "02_冲突且预算耗尽",
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the two approved M1 cases against DeepSeek.")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument(
        "--evidence-root",
        type=Path,
        default=ROOT / "verification" / "api-runs" / "20260923-deepseek-m1",
    )
    args = parser.parse_args()
    api_key = getpass.getpass("DeepSeek API key (memory only, not stored): ")
    config = ApiConfig(base_url=args.base_url, model=args.model, api_key=api_key, timeout_seconds=90)
    client = ChatCompletionsClient(config)
    assets = M1Assets.load(ROOT / "resources" / "prompts")
    examples = ROOT / "resources" / "prompts" / "examples"
    failures = 0

    for name in CASES:
        payload = json.loads((examples / f"{name}.input.json").read_text(encoding="utf-8"))
        workflow = Phase12Workflow(SessionState.new(), assets, args.evidence_root)
        try:
            outcome = workflow.invoke_m1(
                payload,
                client,
                protocol=PROTOCOL_ID,
                configured_model=config.model,
                request_parameters={
                    "protocol": config.protocol,
                    "base_url": config.base_url,
                    "model": config.model,
                    "timeout_seconds": config.timeout_seconds,
                    "temperature": 0,
                    "response_format": "json_object",
                },
            )
        except M1CallFailure as exc:
            failures += 1
            print(f"{name}: returned but failed M1 validation; evidence={exc.evidence_dir}")
        except Exception as exc:
            failures += 1
            print(f"{name}: API call failed; type={type(exc).__name__}; message={exc}")
        else:
            usage = outcome.api_result.usage or {}
            print(
                f"{name}: valid; latency_ms={outcome.api_result.latency_ms}; "
                f"total_tokens={usage.get('total_tokens')}; evidence={outcome.evidence_dir}"
            )
    api_key = ""
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
