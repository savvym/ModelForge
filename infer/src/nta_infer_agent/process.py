from __future__ import annotations

import asyncio
from collections.abc import Sequence


class CommandError(RuntimeError):
    def __init__(self, command: Sequence[str], returncode: int, stderr: str) -> None:
        super().__init__(f"{' '.join(command)} failed with code {returncode}: {stderr.strip()}")
        self.command = command
        self.returncode = returncode
        self.stderr = stderr


async def run_command(
    command: Sequence[str],
    *,
    timeout: float | None = None,
    check: bool = True,
) -> str:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
    except TimeoutError:
        process.kill()
        await process.wait()
        raise

    stdout_text = stdout.decode(errors="replace")
    stderr_text = stderr.decode(errors="replace")
    if check and process.returncode:
        raise CommandError(command, process.returncode, stderr_text)
    return stdout_text.strip()
