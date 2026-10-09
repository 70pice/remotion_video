from pathlib import Path

from videoagents.contracts import ComponentEntry
from videoagents.default_config import PROJECT_ROOT
from videoagents.tools.components import component_manifest


def component_catalog(root: Path = PROJECT_ROOT) -> list[ComponentEntry]:
    # ``root`` remains in the public signature for callers/tests that inject a
    # project root. The packaged manifest is authoritative so a wheel behaves
    # exactly like a source checkout.
    del root
    return [
        ComponentEntry(
            component_id=entry["component_id"],
            name=entry["name"],
            description=entry["description"],
            use_case=entry["use_case"],
            library=entry["library"],
            kind=entry["kind"],
            props_mode=entry["props_mode"],
            orientation=entry["orientation"],
            production_ready=entry["production_ready"],
            min_frames=entry["min_frames"],
            allowed_usages=entry["allowed_usages"],
            license_note=entry["license_note"],
        )
        for entry in component_manifest()
    ]
