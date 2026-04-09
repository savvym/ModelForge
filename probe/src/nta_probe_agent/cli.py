from __future__ import annotations

import argparse
import asyncio
import contextlib
from pathlib import Path

from nta_probe_agent.agent import ProbeAgent
from nta_probe_agent.config import ProbeAgentConfig


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NTA probe agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Run the probe agent loop")
    run_parser.add_argument("--server-base-url", default=None)
    run_parser.add_argument("--project-id", default=None)
    run_parser.add_argument("--registration-token", default=None)
    run_parser.add_argument("--probe-name", default=None)
    run_parser.add_argument("--display-name", default=None)
    run_parser.add_argument("--tags", default=None)
    run_parser.add_argument("--heartbeat-interval", type=int, default=None)
    run_parser.add_argument("--poll-interval", type=int, default=None)
    run_parser.add_argument("--state-path", default=None)
    run_parser.add_argument("--work-dir", default=None)
    run_parser.add_argument("--evalscope-bin", default=None)
    return parser


async def _run_agent(args: argparse.Namespace) -> None:
    config = ProbeAgentConfig.from_env()
    if args.server_base_url:
        config = _replace(config, server_base_url=args.server_base_url.rstrip("/"))
    if args.project_id:
        config = _replace(config, project_id=args.project_id)
    if args.registration_token:
        config = _replace(config, registration_token=args.registration_token)
    if args.probe_name:
        config = _replace(config, probe_name=args.probe_name)
    if args.display_name:
        config = _replace(config, display_name=args.display_name)
    if args.tags is not None:
        config = _replace(
            config,
            tags=[item.strip() for item in args.tags.split(",") if item.strip()],
        )
    if args.heartbeat_interval:
        config = _replace(config, heartbeat_interval_seconds=args.heartbeat_interval)
    if args.poll_interval:
        config = _replace(config, poll_interval_seconds=args.poll_interval)
    if args.state_path:
        config = _replace(config, state_path=Path(args.state_path))
    if args.work_dir:
        config = _replace(config, work_dir=Path(args.work_dir))
    if args.evalscope_bin:
        config = _replace(config, evalscope_bin=args.evalscope_bin)

    agent = ProbeAgent(config)
    try:
        await agent.run_forever()
    finally:
        await agent.aclose()


def _replace(config: ProbeAgentConfig, **changes) -> ProbeAgentConfig:
    values = config.__dict__.copy()
    values.update(changes)
    return ProbeAgentConfig(**values)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    if args.command == "run":
        with contextlib.suppress(KeyboardInterrupt):
            asyncio.run(_run_agent(args))
