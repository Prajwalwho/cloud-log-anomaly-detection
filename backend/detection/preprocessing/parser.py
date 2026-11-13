"""
Log template extraction with Drain (drain3).

Drain groups log messages with the same structure into clusters (templates) and replaces the
variable parts with wildcards, for example:
    "PacketResponder 1 for block blk_-1608 terminating"
    -> "PacketResponder <NUM> for block <BLK> terminating"

Masking replaces well-known variable values (block ids, IPs, UUIDs, hex values, file paths,
numbers) BEFORE Drain sees the message. Drain then does not have to discover these variables
itself, which makes templates more accurate, and allows a stricter similarity threshold so that
messages differing in a real word (e.g. "terminating" vs "Interrupted.") stay separate.

Mask sets:
- DEFAULT_MASKS:      generic; used for HDFS (and, with additions, BGL) in the offline research.
- SERVICE_LOG_MASKS:  DEFAULT_MASKS plus alphanumeric identifiers (user ids like "u6601",
                      transaction ids like "txn_c9731bc4b8"); used for the simulated microservice
                      logs and the live detection service.

A persistence handler (drain3 FilePersistence) can be passed to load a saved parser state;
model packages use this so template ids stay identical between training and live detection.
"""
from __future__ import annotations

from dataclasses import dataclass

from drain3 import TemplateMiner
from drain3.masking import MaskingInstruction
from drain3.persistence_handler import PersistenceHandler
from drain3.template_miner_config import TemplateMinerConfig

# Order matters: specific patterns first, generic numbers last.
# Masks are applied one after another, so later patterns see the output of earlier ones
# (e.g. a path ending in a block id becomes "<PATH>/<BLK>").
DEFAULT_MASKS: tuple[tuple[str, str], ...] = (
    (r"blk_-?\d+", "BLK"),
    (r"(\d{1,3}\.){3}\d{1,3}(:\d+)?", "IP"),
    (r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b", "UUID"),
    (r"\b0x[0-9a-fA-F]+\b", "HEX"),
    (r"(/[\w.\-]+){2,}", "PATH"),                     # file paths with at least two segments
    (r"(?<![A-Za-z0-9_])-?\d+(\.\d+)?(?![A-Za-z0-9_])", "NUM"),
)

# Microservice logs: identifiers that mix letters and digits (u6601, txn_c9731bc4b8) are variables.
# Inserted before the generic NUM mask. Kept out of DEFAULT_MASKS so the offline HDFS/BGL results,
# which were produced with DEFAULT_MASKS, remain reproducible.
ALNUM_ID_MASK: tuple[str, str] = (r"\b(?=\w*[A-Za-z])(?=\w*\d)\w+\b", "ID")
SERVICE_LOG_MASKS: tuple[tuple[str, str], ...] = DEFAULT_MASKS[:-1] + (ALNUM_ID_MASK,) + DEFAULT_MASKS[-1:]

# Similarity threshold chosen experimentally on the first 200,000 HDFS lines (devlog day 13):
# 0.5 and 0.7 gave identical results and merged messages differing in one real word
# ("terminating" vs "Interrupted.", "SocketTimeoutException" vs "EOFException", 4 of 5 words equal
# = 0.8 similarity). 0.9 separated exactly those and left every other template unchanged,
# because masking already removes the variable values.
DEFAULT_SIM_THRESHOLD = 0.9
DEFAULT_DEPTH = 4


@dataclass(frozen=True)
class Template:
    template_id: int
    template: str
    count: int


def create_template_miner(
    sim_threshold: float = DEFAULT_SIM_THRESHOLD,
    depth: int = DEFAULT_DEPTH,
    masks: tuple[tuple[str, str], ...] = DEFAULT_MASKS,
    persistence: PersistenceHandler | None = None,
) -> TemplateMiner:
    """
    A Drain template miner with masking; feed messages with miner.add_log_message(text).
    With a persistence handler, a previously saved parser state is loaded at creation.
    """
    config = TemplateMinerConfig()
    config.drain_sim_th = sim_threshold
    config.drain_depth = depth
    config.masking_instructions = [MaskingInstruction(pattern, name) for pattern, name in masks]
    config.mask_prefix = "<"
    config.mask_suffix = ">"
    config.profiling_enabled = False
    return TemplateMiner(persistence_handler=persistence, config=config)


def templates_of(miner: TemplateMiner) -> list[Template]:
    """Current templates of a miner, ordered by id."""
    templates = [Template(c.cluster_id, c.get_template(), c.size) for c in miner.drain.clusters]
    return sorted(templates, key=lambda t: t.template_id)