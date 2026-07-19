"""Pre-processing module for PVT and rock-property pipeline.

Exports the public API for building PVT blocks from fluid descriptors.
"""

from opm_ai.preprocess.pvt_builder import (
    FluidDescriptor,
    PVTBlocks,
    UnitSystem,
    CorrelationName,
    build_pvt_blocks,
    recommend_correlation,
    validate_pvt_blocks,
    AmbiguousCorrelation,
)

__all__ = [
    "FluidDescriptor",
    "PVTBlocks",
    "UnitSystem",
    "CorrelationName",
    "build_pvt_blocks",
    "recommend_correlation",
    "validate_pvt_blocks",
    "AmbiguousCorrelation",
]