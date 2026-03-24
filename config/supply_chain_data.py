"""
Supply Chain Intelligence — structured data for visualization.

This is the STATIC knowledge base that powers the Supply Chain Map page.
It captures how companies earn revenue, how their products are made,
and the upstream-downstream flow of the supply chain.

This data changes infrequently (only on major business model shifts).
It is curated from 10-K filings and public disclosures.

DATA STRUCTURE PER COMPANY:
    revenue_segments: dict of {segment_name: {pct, description}}
    cost_inputs:      dict of {input_category: {pct, source_description}}
    products:         list of key products/services
    supply_chain:     role, supplies_to, receives_from
"""

# ═══════════════════════════════════════════════════════════════════
#  AI & SEMICONDUCTORS
# ═══════════════════════════════════════════════════════════════════

AI_SEMICONDUCTORS = {
    "sector_name": "AI & Semiconductors",
    "sector_id": "ai_semiconductors",
    "description": "The AI compute supply chain: chips → servers → data centers → energy → end users",
    "chain_layers": [
        {"name": "Raw Materials & IP", "color": "#B0BEC5"},
        {"name": "Fabrication", "color": "#90CAF9"},
        {"name": "Chip Design", "color": "#81C784"},
        {"name": "Server Assembly", "color": "#FFB74D"},
        {"name": "Cloud & AI Platforms", "color": "#CE93D8"},
        {"name": "Energy Infrastructure", "color": "#F06292"},
    ],
    "companies": {
        "TSM": {
            "name": "Taiwan Semiconductor (TSMC)",
            "layer": "Fabrication",
            "revenue_segments": {
                "Advanced Process (≤7nm)": {"pct": 67, "description": "AI/HPC chips, smartphone SoCs — N3/N5/N7 nodes"},
                "Mature Process (>7nm)": {"pct": 17, "description": "Automotive, IoT, power management ICs"},
                "Advanced Packaging": {"pct": 10, "description": "CoWoS, InFO — critical for AI chip packaging"},
                "Mask Making & Other": {"pct": 6, "description": "Photomask, testing, and design services"},
            },
            "cost_inputs": {
                "Raw Silicon Wafers": {"pct": 18, "source": "Shin-Etsu, SUMCO (Japan)"},
                "Chemicals & Gases": {"pct": 14, "source": "Entegris, Air Liquide, Linde"},
                "Photolithography Equipment": {"pct": 22, "source": "ASML (Netherlands) — EUV monopoly"},
                "Other Equipment & Maintenance": {"pct": 16, "source": "Applied Materials, Lam Research, KLA"},
                "Labor & R&D": {"pct": 18, "source": "50,000+ engineers in Taiwan"},
                "Energy & Utilities": {"pct": 12, "source": "Taipower — TSMC uses ~6% of Taiwan's electricity"},
            },
            "products": ["N3E chips", "N5 chips", "CoWoS packaging", "InFO packaging"],
            "supplies_to": ["NVDA", "AMD", "AVGO"],
            "receives_from": ["ASML", "Applied Materials", "Shin-Etsu"],
        },
        "NVDA": {
            "name": "NVIDIA",
            "layer": "Chip Design",
            "revenue_segments": {
                "Data Center": {"pct": 88, "description": "H100/H200/B200 GPUs, DGX systems, networking (InfiniBand/NVLink)"},
                "Gaming": {"pct": 7, "description": "GeForce GPUs for PC gaming"},
                "Professional Visualization": {"pct": 3, "description": "RTX workstation GPUs, Omniverse"},
                "Automotive": {"pct": 2, "description": "DRIVE Orin/Thor for autonomous vehicles"},
            },
            "cost_inputs": {
                "Chip Fabrication (TSMC)": {"pct": 35, "source": "TSMC — all chips manufactured at N4/N5 nodes"},
                "Advanced Packaging (CoWoS)": {"pct": 15, "source": "TSMC — CoWoS packaging is the bottleneck"},
                "Memory (HBM)": {"pct": 20, "source": "SK Hynix (80%), Samsung, Micron"},
                "Substrates & PCBs": {"pct": 8, "source": "Ibiden, Shinko Electric (Japan)"},
                "R&D": {"pct": 18, "source": "30,000+ engineers, CUDA software ecosystem"},
                "Assembly & Test": {"pct": 4, "source": "ASE Technology, Amkor"},
            },
            "products": ["H200 GPU", "B200 GPU", "GB200 NVL72", "DGX systems", "InfiniBand networking"],
            "supplies_to": ["SMCI", "MSFT", "GOOGL", "META", "AMZN"],
            "receives_from": ["TSM"],
        },
        "AMD": {
            "name": "Advanced Micro Devices",
            "layer": "Chip Design",
            "revenue_segments": {
                "Data Center": {"pct": 50, "description": "EPYC server CPUs, Instinct MI300X AI accelerators"},
                "Client": {"pct": 25, "description": "Ryzen desktop/laptop CPUs"},
                "Gaming": {"pct": 12, "description": "Radeon GPUs, Xbox/PlayStation console chips"},
                "Embedded": {"pct": 13, "description": "Xilinx FPGAs, adaptive SoCs"},
            },
            "cost_inputs": {
                "Chip Fabrication (TSMC)": {"pct": 40, "source": "TSMC — N4/N5 for Zen 5, N6 for Xilinx"},
                "Memory (HBM)": {"pct": 12, "source": "SK Hynix, Samsung — for MI300X"},
                "Substrates": {"pct": 10, "source": "Ibiden, Unimicron"},
                "R&D": {"pct": 25, "source": "15,000+ engineers"},
                "Assembly & Test": {"pct": 8, "source": "ASE, SPIL, Amkor"},
                "IP Licensing": {"pct": 5, "source": "ARM (for embedded), various patents"},
            },
            "products": ["EPYC 9005", "MI300X GPU", "Ryzen 9000", "Versal FPGAs"],
            "supplies_to": ["SMCI", "MSFT", "GOOGL", "AMZN"],
            "receives_from": ["TSM"],
        },
        "AVGO": {
            "name": "Broadcom",
            "layer": "Chip Design",
            "revenue_segments": {
                "Infrastructure Software": {"pct": 43, "description": "VMware, mainframe, cybersecurity (CA, Symantec)"},
                "AI Networking": {"pct": 22, "description": "Tomahawk/Jericho switches, AI XPUs for Google/Meta"},
                "Server Storage": {"pct": 12, "description": "SAS/RAID controllers, fiber channel HBAs"},
                "Broadband & Wireless": {"pct": 15, "description": "Wi-Fi 7 chips, cable modem SoCs, Bluetooth"},
                "Industrial & Other": {"pct": 8, "description": "Fiber optic transceivers, LED drivers"},
            },
            "cost_inputs": {
                "Chip Fabrication": {"pct": 28, "source": "TSMC (advanced), GlobalFoundries (mature)"},
                "VMware / Software R&D": {"pct": 22, "source": "Internal — $69B VMware acquisition (2023)"},
                "R&D (Semiconductor)": {"pct": 20, "source": "Custom ASIC design for hyperscalers"},
                "Substrates & Packaging": {"pct": 12, "source": "ASE, Amkor — advanced packaging"},
                "IP Licensing": {"pct": 8, "source": "Various RF/wireless patents"},
                "Test & Assembly": {"pct": 10, "source": "Outsourced OSAT partners"},
            },
            "products": ["Tomahawk 5 switch", "Custom AI XPUs", "VMware Cloud Foundation", "Wi-Fi 7 chips"],
            "supplies_to": ["GOOGL", "META", "MSFT"],
            "receives_from": ["TSM"],
        },
        "SMCI": {
            "name": "Super Micro Computer",
            "layer": "Server Assembly",
            "revenue_segments": {
                "AI/GPU Server Systems": {"pct": 65, "description": "NVIDIA GPU racks (DGX-compatible), liquid-cooled AI clusters"},
                "Storage Systems": {"pct": 15, "description": "Enterprise storage, JBOF, NVMe arrays"},
                "Traditional Server/IT": {"pct": 12, "description": "Standard rack/blade servers, edge computing"},
                "Subsystems & Accessories": {"pct": 8, "description": "Motherboards, chassis, power supplies sold separately"},
            },
            "cost_inputs": {
                "GPUs (NVIDIA)": {"pct": 45, "source": "NVIDIA — H100/H200 GPUs (largest cost component)"},
                "CPUs": {"pct": 12, "source": "AMD EPYC, Intel Xeon"},
                "Memory (DDR5 / HBM)": {"pct": 10, "source": "Samsung, SK Hynix, Micron"},
                "Power Supplies & Cooling": {"pct": 10, "source": "Delta Electronics, in-house liquid cooling"},
                "PCBs & Chassis": {"pct": 8, "source": "In-house manufacturing (San Jose, Taiwan, Netherlands)"},
                "Storage (SSDs)": {"pct": 8, "source": "Samsung, Western Digital, Solidigm"},
                "Assembly Labor": {"pct": 7, "source": "In-house assembly lines"},
            },
            "products": ["GPU SuperCluster", "SuperBlade", "Liquid-cooled racks", "JumpStart AI appliances"],
            "supplies_to": ["MSFT", "GOOGL", "META", "AMZN"],
            "receives_from": ["NVDA", "AMD"],
        },
        "MSFT": {
            "name": "Microsoft",
            "layer": "Cloud & AI Platforms",
            "revenue_segments": {
                "Intelligent Cloud (Azure)": {"pct": 44, "description": "Azure cloud, AI services, SQL Server, GitHub, Enterprise"},
                "Productivity (Office 365)": {"pct": 33, "description": "Office 365, LinkedIn, Dynamics 365, Copilot"},
                "Personal Computing": {"pct": 23, "description": "Windows, Xbox, Surface, Search (Bing + AI)"},
            },
            "cost_inputs": {
                "Data Center Capex": {"pct": 30, "source": "Servers from SMCI/Dell, GPUs from NVIDIA, land/construction"},
                "OpenAI Partnership": {"pct": 10, "source": "$13B+ investment in OpenAI — exclusive Azure hosting"},
                "Cloud Infrastructure": {"pct": 18, "source": "Networking, storage, cooling — 60+ Azure regions"},
                "R&D & Engineering": {"pct": 22, "source": "220,000+ employees, Copilot AI development"},
                "Content & Traffic (LinkedIn/Bing)": {"pct": 8, "source": "Content acquisition, search traffic costs"},
                "Energy & PPA": {"pct": 12, "source": "Nuclear PPA with Constellation Energy, renewables"},
            },
            "products": ["Azure AI", "Copilot", "Office 365", "GitHub Copilot", "Windows"],
            "supplies_to": ["end_users"],
            "receives_from": ["NVDA", "AMD", "SMCI", "CEG"],
        },
        "GOOGL": {
            "name": "Alphabet (Google)",
            "layer": "Cloud & AI Platforms",
            "revenue_segments": {
                "Google Search & Ads": {"pct": 57, "description": "Search advertising, Google Ads network"},
                "YouTube": {"pct": 10, "description": "YouTube advertising and YouTube Premium/TV"},
                "Google Cloud (GCP)": {"pct": 13, "description": "Cloud infrastructure, Vertex AI, BigQuery, Workspace"},
                "Google Services (Other)": {"pct": 12, "description": "Play Store, Pixel, Fitbit, Maps, Chrome"},
                "Other Bets": {"pct": 1, "description": "Waymo, Verily, DeepMind (now integrated), Wing"},
                "Google Subscriptions": {"pct": 7, "description": "YouTube Premium, Google One, Pixel subscriptions"},
            },
            "cost_inputs": {
                "Data Center Capex": {"pct": 28, "source": "Custom TPUs, servers, networking (40+ data centers)"},
                "Traffic Acquisition (TAC)": {"pct": 20, "source": "Payments to Apple ($20B+/yr), browsers, carriers"},
                "R&D": {"pct": 22, "source": "190,000+ employees, Gemini AI development"},
                "Content (YouTube)": {"pct": 12, "source": "Creator payments, music licensing, sports rights"},
                "Networking & Subsea Cables": {"pct": 8, "source": "Private subsea fiber optic cable network"},
                "Energy": {"pct": 10, "source": "24/7 carbon-free energy goal, nuclear SMR deals"},
            },
            "products": ["Google Search", "Gemini AI", "Google Cloud", "YouTube", "Android"],
            "supplies_to": ["end_users"],
            "receives_from": ["NVDA", "AVGO", "SMCI"],
        },
        "META": {
            "name": "Meta Platforms",
            "layer": "Cloud & AI Platforms",
            "revenue_segments": {
                "Family of Apps (Advertising)": {"pct": 97, "description": "Facebook, Instagram, WhatsApp, Messenger ads"},
                "Reality Labs": {"pct": 2, "description": "Quest VR headsets, Ray-Ban Meta glasses, Horizon Worlds"},
                "Other Revenue": {"pct": 1, "description": "Business messaging (WhatsApp Business), payments"},
            },
            "cost_inputs": {
                "AI Infrastructure (Capex)": {"pct": 32, "source": "NVIDIA GPUs, custom MTIA chips, data centers"},
                "R&D": {"pct": 28, "source": "72,000+ employees, Llama AI models, Reality Labs"},
                "Cost of Revenue (Infra)": {"pct": 18, "source": "Data center operations, partner payments"},
                "Reality Labs R&D": {"pct": 12, "source": "$15B+/yr — Quest, Orion AR glasses, neural interfaces"},
                "Marketing & Sales": {"pct": 6, "source": "User acquisition, brand advertising"},
                "Energy": {"pct": 4, "source": "Renewable energy PPAs, nuclear commitments"},
            },
            "products": ["Facebook", "Instagram", "WhatsApp", "Llama AI", "Quest VR"],
            "supplies_to": ["end_users"],
            "receives_from": ["NVDA", "AVGO", "SMCI"],
        },
        "AMZN": {
            "name": "Amazon",
            "layer": "Cloud & AI Platforms",
            "revenue_segments": {
                "Online Stores": {"pct": 40, "description": "Direct e-commerce product sales"},
                "AWS (Cloud)": {"pct": 18, "description": "Cloud computing, Bedrock AI, Trainium chips"},
                "Third-Party Seller Services": {"pct": 24, "description": "FBA, marketplace commissions, advertising"},
                "Advertising": {"pct": 8, "description": "Sponsored products, display ads, Prime Video ads"},
                "Subscriptions (Prime)": {"pct": 7, "description": "Amazon Prime, Kindle Unlimited, Audible"},
                "Physical Stores & Other": {"pct": 3, "description": "Whole Foods, Amazon Go, other revenue"},
            },
            "cost_inputs": {
                "Fulfillment & Logistics": {"pct": 30, "source": "Warehouses, delivery fleet, last-mile delivery"},
                "AWS Infrastructure": {"pct": 20, "source": "Custom Graviton/Trainium chips, servers, networking"},
                "Technology & R&D": {"pct": 18, "source": "Alexa, Bedrock AI, robotics, 1.5M+ employees"},
                "Content (Prime Video)": {"pct": 10, "source": "Original content, sports rights ($1B+ NFL)"},
                "Cost of Products Sold": {"pct": 15, "source": "1P inventory — electronics, groceries, essentials"},
                "Energy": {"pct": 7, "source": "Largest corporate buyer of renewable energy globally"},
            },
            "products": ["Amazon.com", "AWS", "Alexa", "Prime Video", "Trainium chips"],
            "supplies_to": ["end_users"],
            "receives_from": ["NVDA", "AMD", "SMCI", "CEG"],
        },
        "CEG": {
            "name": "Constellation Energy",
            "layer": "Energy Infrastructure",
            "revenue_segments": {
                "Nuclear Generation": {"pct": 55, "description": "21 nuclear reactors — largest US nuclear fleet, 24/7 baseload"},
                "Natural Gas & Other": {"pct": 15, "description": "Gas peaker plants, hydro, wind, solar generation"},
                "Power Marketing & Trading": {"pct": 18, "description": "Wholesale energy trading, hedging strategies"},
                "Retail Energy Supply": {"pct": 12, "description": "Direct retail electricity to businesses & consumers"},
            },
            "cost_inputs": {
                "Nuclear Fuel (Uranium)": {"pct": 15, "source": "Cameco, Kazatomprom — enriched uranium fuel assemblies"},
                "Operations & Maintenance": {"pct": 35, "source": "Plant maintenance, NRC regulatory compliance, workforce"},
                "Natural Gas Fuel": {"pct": 12, "source": "Spot/forward gas market for non-nuclear plants"},
                "Purchased Power": {"pct": 15, "source": "Grid power purchases to meet retail obligations"},
                "Depreciation & Capital": {"pct": 15, "source": "Plant life extension investments, license renewals"},
                "Regulatory & Insurance": {"pct": 8, "source": "NRC licensing, nuclear liability insurance"},
            },
            "products": ["Carbon-free nuclear electricity", "Power purchase agreements (PPAs)", "Clean energy certificates"],
            "supplies_to": ["MSFT", "AMZN"],
            "receives_from": ["Cameco", "NRC"],
        },
    },
    "key_flows": [
        {"from": "Raw Silicon", "to": "TSM", "label": "Silicon wafers", "value": 18},
        {"from": "ASML", "to": "TSM", "label": "EUV lithography", "value": 22},
        {"from": "TSM", "to": "NVDA", "label": "Chip fabrication", "value": 35},
        {"from": "TSM", "to": "AMD", "label": "Chip fabrication", "value": 40},
        {"from": "TSM", "to": "AVGO", "label": "Chip fabrication", "value": 28},
        {"from": "SK Hynix", "to": "NVDA", "label": "HBM memory", "value": 20},
        {"from": "NVDA", "to": "SMCI", "label": "GPUs", "value": 45},
        {"from": "AMD", "to": "SMCI", "label": "CPUs", "value": 12},
        {"from": "SMCI", "to": "MSFT", "label": "AI servers", "value": 30},
        {"from": "SMCI", "to": "GOOGL", "label": "AI servers", "value": 25},
        {"from": "SMCI", "to": "META", "label": "AI servers", "value": 25},
        {"from": "SMCI", "to": "AMZN", "label": "AI servers", "value": 20},
        {"from": "NVDA", "to": "MSFT", "label": "Direct GPU sales", "value": 20},
        {"from": "NVDA", "to": "GOOGL", "label": "Direct GPU sales", "value": 15},
        {"from": "NVDA", "to": "META", "label": "Direct GPU sales", "value": 18},
        {"from": "AVGO", "to": "GOOGL", "label": "Custom AI XPUs", "value": 22},
        {"from": "AVGO", "to": "META", "label": "Network switches", "value": 15},
        {"from": "CEG", "to": "MSFT", "label": "Nuclear PPA", "value": 12},
        {"from": "CEG", "to": "AMZN", "label": "Clean energy", "value": 7},
        {"from": "Uranium", "to": "CEG", "label": "Nuclear fuel", "value": 15},
        {"from": "MSFT", "to": "End Users", "label": "Azure AI / Copilot", "value": 44},
        {"from": "GOOGL", "to": "End Users", "label": "Search / Gemini / GCP", "value": 57},
        {"from": "META", "to": "End Users", "label": "Social / Llama AI", "value": 97},
        {"from": "AMZN", "to": "End Users", "label": "AWS / E-commerce", "value": 40},
    ],
}

# ═══════════════════════════════════════════════════════════════════
#  SPACE & ROCKET TECHNOLOGY
# ═══════════════════════════════════════════════════════════════════

SPACE_ROCKETS = {
    "sector_name": "Space & Rocket Technology",
    "sector_id": "space_rockets",
    "description": "Launch vehicles → satellites → ground infrastructure → space services",
    "chain_layers": [
        {"name": "Components & Propulsion", "color": "#B0BEC5"},
        {"name": "Launch Vehicles", "color": "#90CAF9"},
        {"name": "Satellite & Space Systems", "color": "#81C784"},
        {"name": "Communications & Services", "color": "#FFB74D"},
    ],
    "companies": {
        "RKLB": {
            "name": "Rocket Lab USA",
            "layer": "Launch Vehicles",
            "revenue_segments": {
                "Launch Services": {"pct": 35, "description": "Electron small-sat launches (~$7.5M each), Neutron (in development)"},
                "Space Systems": {"pct": 65, "description": "Satellite components, Photon spacecraft bus, solar panels, reaction wheels"},
            },
            "cost_inputs": {
                "Propulsion (Rutherford Engines)": {"pct": 25, "source": "In-house 3D-printed engines — electric turbopump"},
                "Carbon Composite Structures": {"pct": 18, "source": "In-house carbon fiber tanks and fairings"},
                "Avionics & Electronics": {"pct": 15, "source": "In-house + merchant silicon"},
                "Launch Operations": {"pct": 12, "source": "LC-1 (NZ), LC-2 (Virginia) — pad + range costs"},
                "R&D (Neutron)": {"pct": 22, "source": "Neutron medium-lift rocket development"},
                "Solar & Power Systems": {"pct": 8, "source": "SolAero acquisition — space-grade solar cells"},
            },
            "products": ["Electron rocket", "Neutron rocket (dev)", "Photon spacecraft", "Star Tracker", "Reaction Wheels"],
            "supplies_to": ["satellite_operators", "NASA", "DOD"],
            "receives_from": ["Carbon fiber suppliers", "SolAero (in-house)"],
        },
        "BA": {
            "name": "Boeing",
            "layer": "Launch Vehicles",
            "revenue_segments": {
                "Commercial Airplanes": {"pct": 33, "description": "737 MAX, 787 Dreamliner, 777X"},
                "Defense, Space & Security": {"pct": 33, "description": "SLS rocket, Starliner, satellites, military aircraft"},
                "Global Services": {"pct": 27, "description": "Aftermarket parts, maintenance, pilot training"},
                "Boeing Capital": {"pct": 2, "description": "Aircraft financing"},
                "Other / Unallocated": {"pct": 5, "description": "Corporate and intercompany eliminations"},
            },
            "cost_inputs": {
                "Raw Materials (Aluminum, Titanium, Composites)": {"pct": 30, "source": "Alcoa, VSMPO-AVISMA (titanium), Toray (carbon fiber)"},
                "Engines": {"pct": 20, "source": "GE Aerospace (LEAP, GE9X), Rolls-Royce (Trent)"},
                "Avionics & Systems": {"pct": 15, "source": "Honeywell, Collins Aerospace (RTX), L3Harris"},
                "Labor (Union Workforce)": {"pct": 20, "source": "150,000+ employees, IAM union workforce"},
                "Supplier Subassemblies": {"pct": 10, "source": "Spirit AeroSystems (fuselages), Safran (landing gear)"},
                "R&D": {"pct": 5, "source": "SLS, Starliner, MQ-25 Stingray, autonomous systems"},
            },
            "products": ["737 MAX", "787 Dreamliner", "SLS Rocket", "Starliner", "KC-46 Tanker"],
            "supplies_to": ["NASA", "DOD", "airline_operators"],
            "receives_from": ["NOC", "GE Aerospace", "Spirit AeroSystems"],
        },
        "LMT": {
            "name": "Lockheed Martin",
            "layer": "Satellite & Space Systems",
            "revenue_segments": {
                "Aeronautics": {"pct": 40, "description": "F-35 Lightning II, F-16, C-130J, classified programs"},
                "Missiles & Fire Control": {"pct": 18, "description": "THAAD, PAC-3, JASSM, Javelin, hypersonics"},
                "Rotary & Mission Systems": {"pct": 22, "description": "Sikorsky helicopters, radar, C4ISR, Aegis"},
                "Space": {"pct": 20, "description": "GPS III satellites, Orion spacecraft, SBIRS, A2100 buses"},
            },
            "cost_inputs": {
                "Subcontractor Work": {"pct": 35, "source": "Northrop Grumman (F-35 center fuselage), BAE Systems"},
                "Engines (F-35)": {"pct": 15, "source": "Pratt & Whitney (F135 engine) — sole source"},
                "Electronics & Sensors": {"pct": 15, "source": "L3Harris, Raytheon, in-house radar systems"},
                "R&D": {"pct": 12, "source": "Skunk Works (classified), next-gen interceptors"},
                "Raw Materials": {"pct": 10, "source": "Specialty metals, carbon composites, rare earths"},
                "Labor": {"pct": 13, "source": "116,000 employees, cleared workforce for classified programs"},
            },
            "products": ["F-35", "GPS III satellites", "Orion spacecraft", "THAAD", "Sikorsky helicopters"],
            "supplies_to": ["NASA", "DOD", "allied_governments"],
            "receives_from": ["NOC", "Pratt & Whitney"],
        },
        "NOC": {
            "name": "Northrop Grumman",
            "layer": "Components & Propulsion",
            "revenue_segments": {
                "Aeronautics Systems": {"pct": 28, "description": "B-21 Raider stealth bomber, Global Hawk, HALE drones"},
                "Defense Systems": {"pct": 22, "description": "Ammunition, armored vehicles, IBCS, counter-UAS"},
                "Mission Systems": {"pct": 25, "description": "Radar, electronic warfare, cyber, C4ISR networks"},
                "Space Systems": {"pct": 25, "description": "SRBs for SLS/ULA, OmegA, SpaceLogistics MEV satellites"},
            },
            "cost_inputs": {
                "Propellant & Energetics": {"pct": 20, "source": "In-house solid rocket propellant manufacturing"},
                "Advanced Materials": {"pct": 18, "source": "Carbon composites, stealth coatings (proprietary)"},
                "Electronics & Sensors": {"pct": 18, "source": "In-house AESA radar, IR sensors, EW systems"},
                "Subcontractor Assemblies": {"pct": 12, "source": "Various Tier 2/3 defense subcontractors"},
                "R&D": {"pct": 15, "source": "B-21, next-gen ICBM (Sentinel), JADC2"},
                "Labor": {"pct": 17, "source": "95,000+ employees, high-clearance workforce"},
            },
            "products": ["B-21 Raider", "SLS Solid Rocket Boosters", "Global Hawk", "MEV satellites", "IBCS"],
            "supplies_to": ["BA", "LMT", "NASA"],
            "receives_from": ["propellant_suppliers", "composite_manufacturers"],
        },
        "SPCE": {
            "name": "Virgin Galactic",
            "layer": "Launch Vehicles",
            "revenue_segments": {
                "Space Tourism Flights": {"pct": 70, "description": "Suborbital spaceflights (~$450K/ticket, VSS Unity/Delta)"},
                "Scientific Research Payloads": {"pct": 20, "description": "NASA-sponsored microgravity research flights"},
                "Astronaut Training & Other": {"pct": 10, "description": "Pre-flight training programs, merchandise"},
            },
            "cost_inputs": {
                "Aircraft & Spacecraft Manufacturing": {"pct": 35, "source": "In-house — Delta-class spacecraft development"},
                "Operations & Fuel": {"pct": 20, "source": "Launch operations, hybrid rocket motor propellant"},
                "R&D (Delta Class)": {"pct": 25, "source": "Next-gen Delta spacecraft to scale flights"},
                "Spaceport Operations": {"pct": 12, "source": "Spaceport America, New Mexico"},
                "Pilot Training & Safety": {"pct": 8, "source": "Commercial astronaut pilot program"},
            },
            "products": ["VSS Unity flights", "Delta-class spacecraft (dev)", "Research missions"],
            "supplies_to": ["space_tourists", "NASA"],
            "receives_from": ["propellant_suppliers", "avionics_suppliers"],
        },
        "ASTS": {
            "name": "AST SpaceMobile",
            "layer": "Communications & Services",
            "revenue_segments": {
                "Satellite Services (Planned)": {"pct": 85, "description": "Direct-to-cell broadband via BlueBird satellites"},
                "Technology Licensing": {"pct": 15, "description": "Patent licensing, government contracts, spectrum rights"},
            },
            "cost_inputs": {
                "Satellite Manufacturing": {"pct": 40, "source": "In-house — BlueBird satellites with 64m² phased array"},
                "Launch Costs": {"pct": 20, "source": "SpaceX (Falcon 9 rideshare launches)"},
                "Ground Infrastructure": {"pct": 15, "source": "Gateway ground stations, carrier interconnects"},
                "R&D": {"pct": 18, "source": "Phased array antenna technology, beam forming"},
                "Spectrum & Regulatory": {"pct": 7, "source": "FCC licensing, international spectrum coordination"},
            },
            "products": ["BlueBird satellites", "BlueWalker 3 (test satellite)", "Direct-to-cell broadband"],
            "supplies_to": ["telecom_carriers"],
            "receives_from": ["SpaceX", "antenna_suppliers"],
        },
        "GSAT": {
            "name": "Globalstar",
            "layer": "Communications & Services",
            "revenue_segments": {
                "Wholesale Capacity (Apple)": {"pct": 60, "description": "iPhone Emergency SOS via satellite — exclusive Apple contract"},
                "Subscriber Services": {"pct": 25, "description": "Voice, data, IoT connectivity via LEO constellation"},
                "Equipment Sales": {"pct": 15, "description": "Satellite phones, SPOT trackers, IoT devices"},
            },
            "cost_inputs": {
                "Satellite Operations": {"pct": 30, "source": "24 LEO satellites (2nd gen), ground gateways"},
                "New Satellite Construction": {"pct": 20, "source": "MDA Space (next-gen constellation funded by Apple)"},
                "Ground Network": {"pct": 18, "source": "24 ground gateways worldwide"},
                "Spectrum Licensing": {"pct": 12, "source": "L-band and S-band spectrum assets — globally licensed"},
                "Network Operations": {"pct": 12, "source": "Satellite control, customer support, engineering"},
                "Apple Integration R&D": {"pct": 8, "source": "Custom modem integration for iPhone"},
            },
            "products": ["Emergency SOS service", "SPOT satellite messengers", "IoT connectivity", "Sat-Fi2 hotspot"],
            "supplies_to": ["telecom_carriers", "Apple"],
            "receives_from": ["MDA Space", "Thales Alenia Space"],
        },
    },
    "key_flows": [
        {"from": "Propellant", "to": "NOC", "label": "Solid propellant", "value": 20},
        {"from": "Composites", "to": "NOC", "label": "Carbon composites", "value": 18},
        {"from": "NOC", "to": "BA", "label": "SRBs & fuselage", "value": 35},
        {"from": "NOC", "to": "LMT", "label": "F-35 fuselage", "value": 35},
        {"from": "NOC", "to": "NASA", "label": "SLS boosters", "value": 25},
        {"from": "GE Aerospace", "to": "BA", "label": "Jet engines", "value": 20},
        {"from": "P&W", "to": "LMT", "label": "F135 engines", "value": 15},
        {"from": "RKLB", "to": "DOD/NASA", "label": "Small-sat launches", "value": 35},
        {"from": "BA", "to": "NASA", "label": "SLS / Starliner", "value": 33},
        {"from": "LMT", "to": "NASA", "label": "Orion / GPS III", "value": 20},
        {"from": "LMT", "to": "DOD", "label": "F-35 / THAAD", "value": 40},
        {"from": "SpaceX", "to": "ASTS", "label": "Falcon 9 launches", "value": 20},
        {"from": "Apple", "to": "GSAT", "label": "Capacity payments", "value": 60},
        {"from": "GSAT", "to": "End Users", "label": "Emergency SOS", "value": 60},
        {"from": "ASTS", "to": "Telecom", "label": "Cell broadband", "value": 85},
    ],
}

# ═══════════════════════════════════════════════════════════════════
#  OPTICAL & LIGHT COMMUNICATION
# ═══════════════════════════════════════════════════════════════════

OPTICAL_COMMUNICATIONS = {
    "sector_name": "Optical & Light Communication",
    "sector_id": "optical_communications",
    "description": "Fiber optics → transceivers → network equipment → data center interconnects",
    "chain_layers": [
        {"name": "Test & Measurement", "color": "#B0BEC5"},
        {"name": "Optical Components", "color": "#90CAF9"},
        {"name": "Network Platforms", "color": "#81C784"},
        {"name": "Data Center Networking", "color": "#FFB74D"},
    ],
    "companies": {
        "LITE": {
            "name": "Lumentum Holdings",
            "layer": "Optical Components",
            "revenue_segments": {
                "Cloud & Networking": {"pct": 60, "description": "800G/1.6T transceivers, ROADMs, amplifiers for data centers"},
                "Industrial Tech": {"pct": 25, "description": "3D sensing (VCSEL), fiber lasers for manufacturing, lidar"},
                "Telecom": {"pct": 15, "description": "Long-haul DWDM components, coherent transmission modules"},
            },
            "cost_inputs": {
                "III-V Semiconductor Wafers": {"pct": 25, "source": "InP (Indium Phosphide) wafers — II-VI/Coherent, Sumitomo"},
                "Precision Manufacturing": {"pct": 20, "source": "In-house fab (San Jose, Thailand) — clean room"},
                "R&D": {"pct": 22, "source": "800G/1.6T EML lasers, next-gen VCSEL arrays"},
                "Packaging & Assembly": {"pct": 15, "source": "Hermetic packaging, fiber alignment, automated test"},
                "Test Equipment": {"pct": 8, "source": "Keysight, in-house optical test systems"},
                "Raw Materials (Rare Earths)": {"pct": 10, "source": "Erbium, indium, gallium — global commodity markets"},
            },
            "products": ["800G transceivers", "ROADM modules", "VCSEL arrays", "Fiber lasers"],
            "supplies_to": ["CIEN", "ANET", "cloud_providers"],
            "receives_from": ["KEYS", "wafer_suppliers"],
        },
        "COHR": {
            "name": "Coherent Corp",
            "layer": "Optical Components",
            "revenue_segments": {
                "Networking": {"pct": 45, "description": "800G/1.6T transceivers, coherent DSPs, data center optics"},
                "Materials": {"pct": 30, "description": "SiC substrates, II-VI compounds, engineered crystals"},
                "Lasers": {"pct": 25, "description": "CO2 lasers, fiber lasers, excimer — industrial cutting/welding"},
            },
            "cost_inputs": {
                "Semiconductor Materials (SiC, InP)": {"pct": 28, "source": "In-house II-VI compound growth — vertical integration"},
                "Manufacturing (Global Fabs)": {"pct": 22, "source": "22 manufacturing sites across 4 continents"},
                "R&D": {"pct": 20, "source": "1.6T optics, 200G/lane EML, SiC for EVs"},
                "Packaging & Test": {"pct": 12, "source": "Hermetic packaging, burn-in testing, quality assurance"},
                "Equipment & Maintenance": {"pct": 10, "source": "Crystal growth equipment, epitaxy reactors"},
                "Energy (Crystal Growth)": {"pct": 8, "source": "Crystal growth is extremely energy-intensive"},
            },
            "products": ["800G transceivers", "SiC substrates", "InP wafers", "Industrial lasers"],
            "supplies_to": ["CIEN", "ANET", "cloud_providers"],
            "receives_from": ["KEYS", "raw_material_suppliers"],
        },
        "CIEN": {
            "name": "Ciena Corporation",
            "layer": "Network Platforms",
            "revenue_segments": {
                "Networking Platforms": {"pct": 65, "description": "WaveLogic coherent optical systems, packet switches"},
                "Platform Software & Services": {"pct": 20, "description": "Blue Planet automation, MCP, analytics software"},
                "Global Services": {"pct": 15, "description": "Installation, maintenance, network consulting"},
            },
            "cost_inputs": {
                "Optical Components (Transceivers)": {"pct": 25, "source": "Lumentum, Coherent — 400G/800G pluggable optics"},
                "Custom ASICs (WaveLogic)": {"pct": 20, "source": "In-house WaveLogic DSP design, fabbed by TSMC"},
                "Contract Manufacturing": {"pct": 18, "source": "Flex, Celestica — system assembly"},
                "R&D": {"pct": 22, "source": "WaveLogic 6, Blue Planet AI, adaptive networking"},
                "Software Development": {"pct": 10, "source": "Blue Planet analytics, network orchestration"},
                "Test & Validation": {"pct": 5, "source": "Keysight, VIAV — interoperability testing"},
            },
            "products": ["WaveLogic 6 optical engine", "6500 Packet-Optical Platform", "Blue Planet automation"],
            "supplies_to": ["telecom_carriers", "cloud_providers"],
            "receives_from": ["LITE", "COHR", "KEYS"],
        },
        "ANET": {
            "name": "Arista Networks",
            "layer": "Data Center Networking",
            "revenue_segments": {
                "Product Revenue": {"pct": 80, "description": "7800R/7700R switches, 400G/800G platforms, campus Wi-Fi"},
                "Services": {"pct": 20, "description": "CloudVision management, post-sales support, subscriptions"},
            },
            "cost_inputs": {
                "Merchant Silicon": {"pct": 30, "source": "Broadcom (Memory switching ASICs) — custom silicon in development"},
                "Optical Transceivers": {"pct": 15, "source": "Lumentum, Coherent, InnoLight — 400G/800G optics"},
                "Contract Manufacturing": {"pct": 20, "source": "Flex — all hardware assembly outsourced"},
                "R&D": {"pct": 25, "source": "EOS operating system, CloudVision, network telemetry"},
                "Memory & Components": {"pct": 5, "source": "DRAM, flash, power supplies, fans"},
                "Test & Certification": {"pct": 5, "source": "Interoperability testing, qualification"},
            },
            "products": ["7800R4 spine switches", "7060X campus", "CloudVision", "DANZ monitoring"],
            "supplies_to": ["MSFT", "META", "GOOGL"],
            "receives_from": ["LITE", "COHR", "Broadcom"],
        },
        "KEYS": {
            "name": "Keysight Technologies",
            "layer": "Test & Measurement",
            "revenue_segments": {
                "Communications Solutions": {"pct": 55, "description": "5G/6G test, network analyzers, signal generators, protocol test"},
                "Electronic Industrial Solutions": {"pct": 45, "description": "Oscilloscopes, EDA software, automotive test, semiconductor test"},
            },
            "cost_inputs": {
                "Semiconductors & Components": {"pct": 25, "source": "ADCs, DACs, FPGAs — Xilinx, TI, ADI"},
                "Precision Manufacturing": {"pct": 20, "source": "In-house RF calibration labs, clean rooms"},
                "R&D": {"pct": 28, "source": "AI-native test automation, 6G research, quantum test"},
                "Software Development": {"pct": 15, "source": "PathWave EDA, test automation platform"},
                "Materials & Calibration": {"pct": 7, "source": "Precision reference standards, connectors"},
                "Distribution & Support": {"pct": 5, "source": "Global service and calibration centers"},
            },
            "products": ["Network Analyzers", "Signal Generators", "PathWave EDA", "Protocol Test"],
            "supplies_to": ["LITE", "COHR", "CIEN"],
            "receives_from": ["semiconductor_suppliers"],
        },
        "VIAV": {
            "name": "VIAV Solutions",
            "layer": "Test & Measurement",
            "revenue_segments": {
                "Network Enablement (NE)": {"pct": 50, "description": "Fiber test, OTDR, network assurance, 5G field test"},
                "Optical Security & Performance (OSP)": {"pct": 35, "description": "Anti-counterfeiting for currencies, 3D sensing filters"},
                "Service Enablement (SE)": {"pct": 15, "description": "Network performance monitoring, SaaS analytics"},
            },
            "cost_inputs": {
                "Optical Components": {"pct": 22, "source": "Laser diodes, detectors, fiber connectors"},
                "Precision Manufacturing": {"pct": 25, "source": "Thin-film optical coatings, holographic elements"},
                "R&D": {"pct": 22, "source": "AI network assurance, fiber sensing, anti-counterfeit"},
                "Software Development": {"pct": 15, "source": "NITRO platform, Observer analytics"},
                "Materials (Optical Films)": {"pct": 10, "source": "Specialty chemicals, substrates for security products"},
                "Distribution": {"pct": 6, "source": "Direct sales + channel partners globally"},
            },
            "products": ["OTDR fiber testers", "SmartOTDR", "Currency security threads", "Observer analytics"],
            "supplies_to": ["telecom_carriers", "cloud_providers"],
            "receives_from": ["optical_component_suppliers"],
        },
    },
    "key_flows": [
        {"from": "InP Wafers", "to": "LITE", "label": "III-V wafers", "value": 25},
        {"from": "InP Wafers", "to": "COHR", "label": "II-VI compounds", "value": 28},
        {"from": "KEYS", "to": "LITE", "label": "Test equipment", "value": 8},
        {"from": "KEYS", "to": "COHR", "label": "Test equipment", "value": 8},
        {"from": "KEYS", "to": "CIEN", "label": "Protocol test", "value": 5},
        {"from": "LITE", "to": "CIEN", "label": "Transceivers", "value": 25},
        {"from": "COHR", "to": "CIEN", "label": "Transceivers", "value": 20},
        {"from": "LITE", "to": "ANET", "label": "Optics modules", "value": 15},
        {"from": "COHR", "to": "ANET", "label": "Optics modules", "value": 12},
        {"from": "Broadcom", "to": "ANET", "label": "Switch silicon", "value": 30},
        {"from": "CIEN", "to": "Telecom", "label": "WaveLogic systems", "value": 65},
        {"from": "CIEN", "to": "Cloud", "label": "DCI platforms", "value": 20},
        {"from": "ANET", "to": "Microsoft", "label": "DC switches", "value": 30},
        {"from": "ANET", "to": "Meta", "label": "DC switches", "value": 25},
        {"from": "VIAV", "to": "Telecom", "label": "Fiber test tools", "value": 50},
    ],
}


# ═══════════════════════════════════════════════════════════════════
#  REGISTRY
# ═══════════════════════════════════════════════════════════════════

SUPPLY_CHAIN_DATA = {
    "ai_semiconductors": AI_SEMICONDUCTORS,
    "space_rockets": SPACE_ROCKETS,
    "optical_communications": OPTICAL_COMMUNICATIONS,
}


def get_supply_chain(sector_id: str) -> dict | None:
    """Retrieve the full supply chain data for a sector."""
    return SUPPLY_CHAIN_DATA.get(sector_id)


def get_company_data(sector_id: str, ticker: str) -> dict | None:
    """Retrieve company-level supply chain data."""
    sector = SUPPLY_CHAIN_DATA.get(sector_id)
    if not sector:
        return None
    return sector.get("companies", {}).get(ticker)
