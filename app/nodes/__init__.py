"""Importing this package registers every node type."""

from app.nodes import (  # noqa: F401
    audio,
    captions,
    clips,
    export,
    ingest,
    metadata,
    render,
    scenes,
    track,
    transcribe,
)
