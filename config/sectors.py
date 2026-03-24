"""
Sector definitions — the heart of your analysis universe.

Each sector defines:
- name: Human-readable label
- tickers: The stocks to track
- supply_chain_map: How the supply chain flows (this is what makes
  second-order reasoning possible). The AI uses this map to trace
  causal chains: "If X happens to upstream, what happens downstream?"
- keywords: Search terms for filtering relevant news
"""

SECTORS = {
    "ai_semiconductors": {
        "name": "AI & Semiconductors",
        "description": "The AI compute supply chain: chips → servers → data centers → energy → end users",
        "tickers": ["NVDA", "AMD", "TSM", "AVGO", "SMCI", "CEG", "MSFT", "GOOGL", "META", "AMZN"],
        "supply_chain_map": {
            # upstream → downstream relationships
            # Read as: "upstream_company supplies to downstream_companies"
            "TSM":  {"role": "Foundry (chip fabrication)", "supplies_to": ["NVDA", "AMD", "AVGO"]},
            "NVDA": {"role": "GPU designer", "supplies_to": ["SMCI", "MSFT", "GOOGL", "META", "AMZN"]},
            "AMD":  {"role": "CPU/GPU designer", "supplies_to": ["SMCI", "MSFT", "GOOGL", "AMZN"]},
            "AVGO": {"role": "Networking chips & custom AI accelerators", "supplies_to": ["GOOGL", "META", "MSFT"]},
            "SMCI": {"role": "Server assembly", "supplies_to": ["MSFT", "GOOGL", "META", "AMZN"]},
            "MSFT": {"role": "Cloud / AI platform (Azure + OpenAI)", "supplies_to": ["end_users"]},
            "GOOGL":{"role": "Cloud / AI platform (GCP + Gemini)", "supplies_to": ["end_users"]},
            "META": {"role": "AI consumer (Llama models, ads infra)", "supplies_to": ["end_users"]},
            "AMZN": {"role": "Cloud / AI platform (AWS + Trainium)", "supplies_to": ["end_users"]},
            "CEG":  {"role": "Energy provider (nuclear baseload for data centers)", "supplies_to": ["MSFT", "AMZN"]},
        },
        "keywords": ["artificial intelligence", "GPU", "semiconductor", "data center", "AI chip",
                      "machine learning", "neural network", "CUDA", "inference", "training",
                      "TSMC", "nvidia", "AMD", "broadcom", "supermicro"],
    },

    "space_rockets": {
        "name": "Space & Rocket Technology",
        "description": "Launch vehicles → satellites → ground infrastructure → space services",
        "tickers": ["RKLB", "BA", "LMT", "NOC", "SPCE", "ASTS", "GSAT"],
        "supply_chain_map": {
            "RKLB": {"role": "Small launch provider (Electron, Neutron)", "supplies_to": ["satellite_operators"]},
            "BA":   {"role": "Launch provider (SLS, Starliner) + defense", "supplies_to": ["NASA", "DOD"]},
            "LMT":  {"role": "Defense + space systems (Orion, GPS satellites)", "supplies_to": ["NASA", "DOD"]},
            "NOC":  {"role": "Solid rocket boosters + space systems", "supplies_to": ["BA", "LMT", "NASA"]},
            "SPCE": {"role": "Suborbital space tourism", "supplies_to": ["end_users"]},
            "ASTS": {"role": "Space-based cellular broadband (AST SpaceMobile)", "supplies_to": ["telecom_carriers"]},
            "GSAT": {"role": "Satellite communications spectrum holder", "supplies_to": ["telecom_carriers"]},
        },
        "keywords": ["rocket launch", "satellite", "space launch", "orbit", "SpaceX",
                      "Rocket Lab", "Neutron rocket", "Electron rocket", "defense contract",
                      "NASA contract", "space station", "LEO constellation", "spacecraft",
                      "rocket engine", "space industry", "launch vehicle", "Starship",
                      "space force", "missile defense", "Northrop Grumman", "Lockheed Martin",
                      "Boeing defense", "AST SpaceMobile", "Globalstar"],
    },

    "optical_communications": {
        "name": "Optical & Light Communication",
        "description": "Fiber optics → transceivers → network equipment → data center interconnects",
        "tickers": ["LITE", "COHR", "CIEN", "ANET", "KEYS", "VIAV"],
        "supply_chain_map": {
            "LITE": {"role": "Optical components (Lumentum — lasers, transceivers)", "supplies_to": ["CIEN", "ANET", "cloud_providers"]},
            "COHR": {"role": "Optical components (Coherent — II-VI, transceivers, lasers)", "supplies_to": ["CIEN", "ANET", "cloud_providers"]},
            "CIEN": {"role": "Optical networking platforms (Ciena — WaveLogic)", "supplies_to": ["telecom_carriers", "cloud_providers"]},
            "ANET": {"role": "Data center networking (Arista)", "supplies_to": ["MSFT", "META", "GOOGL"]},
            "KEYS": {"role": "Test & measurement for optical/electronic systems", "supplies_to": ["LITE", "COHR", "CIEN"]},
            "VIAV": {"role": "Network test, measurement & assurance (fiber/optical)", "supplies_to": ["telecom_carriers", "cloud_providers"]},
        },
        "keywords": ["optical network", "fiber optic", "transceiver", "photonics", "laser",
                      "coherent optics", "data center interconnect", "DCI",
                      "400G", "800G", "pluggable optics", "silicon photonics",
                      "Lumentum", "Coherent Corp", "Ciena", "Arista Networks", "Infinera",
                      "Keysight", "optical fiber", "network equipment",
                      "data center networking", "cloud networking", "bandwidth demand"],
    },
}


def get_all_tickers() -> list[str]:
    """Return a flat, deduplicated list of every ticker across all sectors."""
    tickers = set()
    for sector in SECTORS.values():
        tickers.update(sector["tickers"])
    return sorted(tickers)


def get_sector_by_id(sector_id: str) -> dict | None:
    """Look up a sector by its key (e.g., 'ai_semiconductors')."""
    return SECTORS.get(sector_id)
