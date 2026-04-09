from __future__ import annotations

import importlib.metadata

try:
    __version__ = importlib.metadata.version("nta-probe-agent")
except importlib.metadata.PackageNotFoundError:
    __version__ = "0.1.0"

from nta_probe_agent.agent import ProbeAgent
from nta_probe_agent.config import ProbeAgentConfig

__all__ = ["ProbeAgent", "ProbeAgentConfig", "__version__"]
