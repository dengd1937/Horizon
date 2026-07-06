"""Deploy the rendered site via a configurable shell command.

The command is cloud-agnostic (coscli sync / rsync / anything); switching
hosting means editing one config line. Credentials come from environment
variables inherited by the subprocess (GitHub Secrets in CI, .env locally).
"""

import asyncio
import logging
from typing import Optional

from ..models import SiteConfig

logger = logging.getLogger(__name__)

DEPLOY_TIMEOUT_SEC = 300.0


async def deploy_site(
    config: SiteConfig, timeout: float = DEPLOY_TIMEOUT_SEC
) -> Optional[bool]:
    """Run site.deploy_command.

    Returns None when no command is configured (local-only mode), True on
    success, False on failure/timeout. Never raises: a broken deploy must
    not take down the rest of the run.
    """
    command = (config.deploy_command or "").strip()
    if not command:
        return None

    logger.info("Deploying site: %s", command)
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=timeout
            )
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            logger.error("Site deploy timed out after %.0fs", timeout)
            return False
    except Exception as exc:
        logger.error("Site deploy failed to start: %s", exc)
        return False

    if proc.returncode != 0:
        detail = (stderr or stdout or b"").decode(errors="replace").strip()
        logger.error("Site deploy exited %d: %s", proc.returncode, detail[-500:])
        return False

    output = (stdout or b"").decode(errors="replace").strip()
    if output:
        logger.info("Site deploy output: %s", output[-300:])
    return True
