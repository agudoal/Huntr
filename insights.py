#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
insights.py  --  Huntr buyer-ranking & thesis engine   (06. Automation)
========================================================================
Turns each scored company into two things the tearsheet renders:

  buyers : a ranked list of NAMED potential acquirers (mostly public
           companies) + named financial sponsors, each with a rationale.
           The ORDER and the fit scores are recomputed every night from
           the live factors, so the section refreshes with the data even
           though the underlying knowledge base is human-curated.

  thesis : a short, structured, four-part read with live figures injected:
             why_now  - the valuation / ownership trigger
             asset    - what is scarce or strategic about the business
             path     - the single most probable route to a deal
             risk     - the key obstacle

THE "HYBRID" MODEL (what refreshes overnight vs what is curated)
  * WHO can buy it            -> curated here (real names, real logic)
  * HOW they rank tonight     -> data-driven (re-ranked from live factors)
  * The NUMBERS in the thesis -> data-driven (injected from nightly JSON)
So Huntr never invents prose at 3am, but the prioritisation and every
figure move with the latest fundamentals. When we later add per-buyer
accretion/dilution, it slots into the same per-buyer structure.

Factors are 0-100 percentiles, higher = more acquisition-friendly:
  f_val cheap vs peers      f_own high free float / low control
  f_bs  clean balance sheet f_sz  small (more able buyers)
  f_sc  sector M&A live      f_si  named-buyer / activist signal
"""

# ---------------------------------------------------------------------------
# 1. NIGHTLY RE-RANKING  --  how each buyer's fit moves with the live data
# ---------------------------------------------------------------------------
# Each buyer has a base fit (inherent plausibility) and a TYPE. The type
# decides which live factors push the fit up or down tonight:
#   strategics care about sector-M&A momentum, scarcity and feasibility/size
#   sponsors   care about cheapness, a clean balance sheet, size and free float
#   sovereigns care mostly about strategic-asset signal
TYPE_TILT = {
    "strat": {"f_sc": 11, "f_si": 10, "f_sz": 8,  "f_val": 5},
    "spons": {"f_val": 12, "f_bs": 9, "f_sz": 12, "f_own": 9},
    "state": {"f_si": 13, "f_sc": 5,  "f_sz": 4},
}

def adj_fit(base, typ, F):
    """Base fit nudged by how favourable tonight's factors are for this buyer type."""
    s = float(base)
    for fk, w in TYPE_TILT.get(typ, {}).items():
        v = F.get(fk)
        if v is None:
            continue
        s += w * (float(v) - 50.0) / 50.0      # factor 50 = neutral; 100 -> +w
    return int(max(20, min(96, round(s))))

def B(name, ticker, typ, base, why):
    return {"n": name, "tk": ticker, "t": typ, "base": base, "why": why}

# ---------------------------------------------------------------------------
# 2. SUBSECTOR BUYER POOLS  --  the "rich tail map"
# ---------------------------------------------------------------------------
# Real, named public acquirers + named sponsors for EVERY name in a subsector.
# This is what replaces the old vague "Software-focused PE / Larger platform".
SUBSECTOR_BUYERS = {
 "pay": [
  B("Fiserv","FI","strat",70,"US payments scale-buyer; acquiring European acquiring/issuing in one move adds distribution and dollar-cheap assets. Antitrust and data-sovereignty review is the main brake."),
  B("Global Payments","GPN","strat",66,"Active consolidator mid-portfolio reshuffle (the Worldpay / issuer-solutions swap with FIS); clear appetite for merchant-acquiring scale."),
  B("Nexi","NEXI.MI","strat",60,"Pan-European acquiring champion built by roll-up (SIA, Nets); overlapping terminal estates make in-market combinations highly synergetic."),
  B("Adyen","ADYEN.AS","strat",50,"Best-in-class single-platform processor; more likely to buy capability or licences than a legacy estate, but a rare strategic European consolidator."),
  B("Advent International","","spons",72,"The most active payments sponsor (Nexi, Worldpay heritage); recurring volumes and cash generation at a depressed multiple are a take-private sweet spot."),
  B("Silver Lake","","spons",64,"Large-cap tech sponsor comfortable underwriting payments platforms and carve-outs."),
  B("Hellman & Friedman","","spons",62,"Long-run payments / fintech investor able to anchor a club deal."),
  B("Brookfield","BN","spons",56,"Infrastructure-style buyer that treats processing rails as a quasi-infrastructure cash-flow asset."),
 ],
 "semis": [
  B("Infineon","IFX.DE","strat",68,"Europe's power / automotive leader; vertical and capacity consolidation amid reshoring and the EU Chips Act."),
  B("STMicroelectronics","STM","strat",62,"Franco-Italian IDM with scale to absorb RF / power / sensor assets; strategic-asset rules favour an EU acquirer."),
  B("NXP Semiconductors","NXPI","strat",60,"Automotive / edge leader that grows by targeted M&A; complementary analog and connectivity IP."),
  B("onsemi","ON","strat",54,"Power / sensing consolidator focused on automotive and industrial end-markets."),
  B("Renesas","6723.T","strat",52,"Acquisitive Japanese IDM (Dialog, Altium) seeking European analog / embedded IP."),
  B("Texas Instruments","TXN","strat",46,"Analog scale-buyer; disciplined but able to absorb a niche franchise."),
  B("KKR","","spons",56,"Large-cap sponsor active in semis / industrial-tech carve-outs."),
  B("Bain Capital","","spons",52,"Semis-experienced sponsor (Toshiba memory heritage) for a take-private or break-up."),
 ],
 "semieq": [
  B("Applied Materials","AMAT","strat",66,"Largest wafer-fab-equipment vendor; tool-portfolio breadth and roadmap control motivate bolt-ons."),
  B("Lam Research","LRCX","strat",62,"Etch / deposition leader extending adjacencies; metrology and specialty tools are logical targets."),
  B("KLA","KLAC","strat",60,"Process-control leader that buys inspection / metrology niches (e.g. Orbotech)."),
  B("ASML","ASML.AS","strat",56,"Litho monopoly; a selective acquirer of enabling metrology, optics and software."),
  B("Tokyo Electron","8035.T","strat",50,"Major WFE consolidator seeking Western metrology / test footholds."),
  B("Onto Innovation","ONTO","strat",46,"Mid-cap metrology consolidator combining complementary inspection lines."),
  B("Carlyle","CG","spons",48,"Industrial-tech sponsor for a niche-monopoly cash-flow play."),
  B("Platinum Equity","","spons",44,"Carve-out specialist suited to a sub-scale equipment franchise."),
 ],
 "cyber": [
  B("Palo Alto Networks","PANW","strat",72,"Most acquisitive security platform (CyberArk, Chronosphere); buys point leaders to extend the suite."),
  B("Cisco","CSCO","strat",62,"Networking-security consolidator (Splunk) with balance-sheet firepower."),
  B("CrowdStrike","CRWD","strat",56,"Endpoint / cloud platform extending into identity, data and SecOps via M&A."),
  B("Check Point","CHKP","strat",54,"Cash-rich and increasingly acquisitive to refresh growth."),
  B("Zscaler","ZS","strat",48,"Zero-trust leader adding adjacent capability."),
  B("Thoma Bravo","","spons",74,"The dominant cybersecurity sponsor (Darktrace, Proofpoint, Sophos); a serial take-private machine."),
  B("Vista Equity Partners","","spons",62,"Enterprise-software / security sponsor for sticky-ARR take-privates."),
  B("Advent International","","spons",54,"Active security sponsor (McAfee enterprise heritage)."),
 ],
 "itserv": [
  B("Accenture","ACN","strat",72,"By far the most active acquirer (~40 deals a year), routinely tucking in mid-cap specialists for capability and geography."),
  B("Capgemini","CAP.PA","strat",66,"European scale consolidator buying digital-engineering and sector depth."),
  B("Cognizant","CTSH","strat",58,"Re-engaging in M&A for European nearshore delivery and industry skills."),
  B("Infosys","INFY","strat",54,"Indian major buying European onshore presence and client relationships."),
  B("IBM","IBM","strat",52,"Consulting / AI-services consolidator (Hakkoda) targeting data and sovereign-AI skills."),
  B("Tata Consultancy Services","TCS.NS","strat",48,"Scale Indian IT buyer seeking a deeper European footprint."),
  B("EQT","","spons",60,"Active services sponsor building nearshore-delivery platforms via buy-and-build."),
  B("Bridgepoint","BPT.L","spons",50,"European mid-market sponsor for cash-generative IT-services roll-ups."),
 ],
 "appsw": [
  B("Thoma Bravo","","spons",74,"The benchmark software-PE take-private buyer; recurring-revenue assets at LBO-friendly scale, now with a dedicated European fund."),
  B("Vista Equity Partners","","spons",68,"Enterprise-software specialist with an operational playbook on sticky ARR."),
  B("Hg","","spons",64,"European software champion-builder; the natural sponsor for many EU SaaS names."),
  B("EQT","","spons",60,"Large EU sponsor (IFS, Dechra) able to take mid / large-caps private."),
  B("SAP","SAP.DE","strat",58,"European software flagship; selective large bolt-ons to extend the cloud suite."),
  B("Microsoft","MSFT","strat",54,"Deep-pocketed platform buyer, though large software deals draw heavy antitrust scrutiny."),
  B("Oracle","ORCL","strat",52,"Vertical-application consolidator with appetite for installed bases."),
  B("Salesforce","CRM","strat",48,"Front-office platform that buys data / workflow adjacencies (Slack, Tableau)."),
 ],
 "infrasw": [
  B("Thoma Bravo","","spons",70,"Infrastructure-software take-private specialist with a deep European pipeline."),
  B("Hg","","spons",60,"European infra-software champion-builder."),
  B("Permira","","spons",56,"Tech sponsor comfortable with mission-critical software carve-outs."),
  B("Cisco","CSCO","strat",62,"Infrastructure / observability consolidator (Splunk, ThousandEyes)."),
  B("IBM","IBM","strat",58,"Hybrid-cloud / automation buyer (HashiCorp, Red Hat heritage)."),
  B("Broadcom","AVGO","strat",54,"Infrastructure-software roll-up (VMware, CA, Symantec) optimised for cash flow."),
  B("Microsoft","MSFT","strat",50,"Cloud / dev-tools platform buyer (GitHub) extending the stack."),
  B("Nokia","NOKIA.HE","strat",44,"Networks player adding software / IP to lift margins."),
 ],
 "internet": [
  B("Prosus / Naspers","PRX.AS","strat",62,"Cash-rich global internet investor consolidating marketplaces and classifieds."),
  B("Permira","","spons",64,"Marketplace / classifieds sponsor (Adevinta, BestSecret)."),
  B("Hellman & Friedman","","spons",62,"Large internet / classifieds sponsor (Adevinta consortium)."),
  B("Blackstone","BX","spons",58,"Mega-cap sponsor for profitable platforms with pricing power."),
  B("Silver Lake","","spons",56,"Tech sponsor for take-privates of cash-generative internet assets."),
  B("Booking Holdings","BKNG","strat",48,"Travel / marketplace platform extending verticals."),
  B("CoStar Group","CSGP","strat",46,"Acquisitive vertical-data / marketplace buyer, especially in property."),
  B("Gartner / vertical-data buyer","IT","strat",44,"B2B data and insight buyers value category-leading proprietary datasets."),
 ],
 "hw": [
  B("Cisco","CSCO","strat",56,"Networking / hardware buyer with broad appetite and firepower."),
  B("Nokia","NOKIA.HE","strat",52,"Networks consolidator (Infinera) seeking optical / IP scale."),
  B("Honeywell","HON","strat",52,"Industrial-tech consolidator of sensing and instrumentation."),
  B("Halma","HLMA.L","strat",50,"Serial buy-and-build acquirer of safety / sensor niche leaders."),
  B("Ericsson","ERIC-B.ST","strat",48,"Networks peer pursuing software and enterprise adjacencies."),
  B("Amphenol","APH","strat",48,"Acquisitive interconnect / sensor consolidator."),
  B("Advent International","","spons",54,"Industrial-tech sponsor for carve-outs and take-privates."),
  B("KKR","","spons",50,"Large-cap sponsor for hardware / industrial cash-flow assets."),
 ],
 "gaming": [
  B("Tencent","0700.HK","strat",70,"The most strategic global gaming buyer; escalates minority stakes to control and backs Western IP."),
  B("Electronic Arts","EA","strat",56,"AAA publisher seeking IP and studio capacity."),
  B("Microsoft","MSFT","strat",52,"Owns Activision / ZeniMax; further large gaming M&A faces regulatory fatigue."),
  B("Take-Two","TTWO","strat",52,"Publisher consolidator (Zynga) extending franchises."),
  B("Sony","6758.T","strat",50,"PlayStation owner acquiring studios and live-service IP."),
  B("Savvy Games / PIF","","state",62,"Saudi sovereign vehicle with explicit gaming ambitions and effectively unlimited capital."),
  B("EQT / KKR (gaming PE)","","spons",50,"Sponsors backing roll-ups of profitable mid-cap studios."),
  B("Embracer","EMBRAC-B.ST","strat",42,"Acquisitive (now deleveraging) studio consolidator."),
 ],
}

# ---------------------------------------------------------------------------
# 3. BESPOKE BUYER LISTS  --  the "top names deep" layer (keyed by FULL ticker)
# ---------------------------------------------------------------------------
NAMED_BUYERS = {
 "TEMN.SW": [
  B("Thoma Bravo","","spons",84,"Reported to be in early-stage takeover talks with Temenos; core-banking software is a textbook software-PE asset (mission-critical, sticky, high renewals) and activist Petrus Advisers has put change on the table."),
  B("EQT","","spons",76,"Named alongside Thoma Bravo as a credible buyout suitor; a large EU sponsor able to take a CHF-listed mid-cap private."),
  B("Vista Equity Partners","","spons",70,"Banking / fintech-software specialist; a natural club or competing bidder for a sticky core-banking franchise."),
  B("Oracle","ORCL","strat",54,"Owns FLEXCUBE core banking; a scale play to consolidate the category."),
  B("SAP","SAP.DE","strat",50,"Could fold banking software into its industry cloud, though less likely than a sponsor."),
 ],
 "WLN.PA": [
  B("Advent International","","spons",84,"Payments take-privates are Advent's sweet spot; with the equity down ~90% from its peak a sponsor can buy recurring volumes cheaply and restructure away from public scrutiny, most likely in pieces."),
  B("Silver Lake","","spons",72,"Large-cap sponsor able to anchor a club deal for a broken-but-cash-generative processor."),
  B("Nexi","NEXI.MI","strat",60,"The long-rumoured European payments merger; overlapping estates and synergy are compelling, but French and Italian governments are cool on a tie-up."),
  B("Credit Agricole","ACA.PA","strat",56,"Already a commercial JV partner and shareholder; could move from partner to owner of the French merchant base as strategic banking infrastructure."),
  B("Global Payments","GPN","strat",50,"US scale-buyer of European distribution; FX-cheap assets, offset by sovereignty and antitrust friction."),
 ],
 "UBI.PA": [
  B("Tencent","0700.HK","strat",84,"Already anchored Ubisoft's IP via a EUR 1.16bn / 25% stake in the new Vantage Studios subsidiary and holds ~10% of the parent; the cleanest path is escalating from minority to control."),
  B("Guillemot family + sponsor","","spons",72,"Founders have signalled they want to protect independence; a sponsor-backed buyout with the family rolling equity removes public-market pressure."),
  B("Savvy Games / PIF","","state",60,"Saudi sovereign vehicle floated as a bidder in early 2025; unlimited capital, but a full bid did not materialise and French strategic-asset sensitivities apply."),
  B("Electronic Arts","EA","strat",48,"AAA IP (Assassin's Creed, Rainbow Six) is coveted, but a US strategic faces regulatory fatigue and French political resistance."),
  B("Microsoft","MSFT","strat",42,"Owns large studios already; further mega-gaming M&A is regulatorily fraught."),
 ],
 "DAVA": [
  B("Accenture","ACN","strat",80,"By far the most active IT-services acquirer; Endava's nearshore digital-engineering delivery and blue-chip client base are an easy tuck-in after a sharp de-rating."),
  B("Capgemini","CAP.PA","strat",72,"European scale consolidator seeking digital-engineering depth and geographic balance."),
  B("EPAM Systems","EPAM","strat",66,"Direct pure-play peer; a merger would build scale and diversify delivery geographies."),
  B("EQT","","spons",62,"Services sponsor able to take a de-rated, cash-generative engineering firm private and re-scale it."),
  B("Cognizant","CTSH","strat",56,"Re-engaging in M&A for European nearshore capacity and skills."),
 ],
 "AMS.SW": [
  B("Industrial / photonics strategic","","strat",64,"Automotive optical-sensing and photonics IP attracts large industrial groups; analysts tie takeover appeal to hitting a ~15% adjusted-EBITDA margin by 2026."),
  B("Infineon","IFX.DE","strat",58,"Sensing / photonics adjacencies complement its automotive and power portfolio."),
  B("PE turnaround consortium","","spons",60,"With >90% free float and deleveraging underway, a sponsor consortium could take a break-up / turnaround position."),
  B("onsemi","ON","strat",52,"Sensing-focused consolidator that could absorb selected optical-sensor lines."),
  B("Apollo / Bain Capital","","spons",48,"Distressed / turnaround sponsors suited to a leveraged, restructuring asset."),
 ],
 "ATO.PA": [
  B("Daniel Kretinsky / EPEI","","spons",78,"Already entangled in the restructuring and a natural distressed acquirer of selected assets; an opportunistic value play on a broken-up balance sheet."),
  B("French State / Bpifrance","","state",76,"Eviden's Advanced Computing and mission-critical-security unit is a sovereign-defence asset (supercomputing, cryptography); the state has moved to secure it."),
  B("Distressed-debt funds","","spons",68,"Creditors converting debt into equity through the restructuring is arguably the most probable control change of all."),
  B("Airbus / Thales","AIR.PA","strat",62,"Defence primes have repeatedly circled the sovereign-critical units; a prime could absorb BDS and leave the rest to financial buyers."),
  B("Capgemini","CAP.PA","strat",38,"Could cherry-pick services assets, but is wary of legacy managed-infrastructure liabilities."),
 ],
 "NEXI.MI": [
  B("Hellman & Friedman","","spons",82,"Large historic sponsor backer; a take-private at a premium to a depressed multiple is the most direct path given the register."),
  B("Advent International","","spons",78,"Payments-PE heavyweight and Nexi-heritage investor able to anchor a club deal."),
  B("Bain Capital","","spons",72,"Co-investor archetype for an Italian payments take-private."),
  B("Worldline","WLN.PA","strat",56,"Mirror-image merger of European payments scale players; large synergy but political friction."),
  B("Global Payments","GPN","strat",50,"US strategic consolidation of European acquiring; sovereignty and antitrust are the constraints."),
 ],
 "ALLFG.AS": [
  B("Euronext","ENX.PA","strat",70,"Made an approach for Allfunds in 2023; European market-infrastructure consolidators value the fund-distribution network and the data on it."),
  B("Hellman & Friedman","","spons",66,"Existing major shareholder; could anchor a take-private of a cash-generative network asset."),
  B("BlackRock","BLK","strat",60,"Strategic interest in fund-distribution / wealthtech rails; a platform play on European fund flows."),
  B("Deutsche Boerse","DB1.DE","strat",56,"Market-infrastructure / data consolidator extending into fund distribution."),
  B("Permira","","spons",54,"Wealthtech / fintech sponsor for a platform take-private."),
 ],
 "EVO.ST": [
  B("EQT","","spons",60,"Nordic large-cap sponsor able to take a cash-rich, founder-influenced leader private after the valuation reset."),
  B("CVC Capital Partners","","spons",56,"Gaming-experienced sponsor for a cash-generative take-private."),
  B("Light & Wonder","LNW","strat",54,"Gaming-supplier consolidator that could combine land-based / digital content with live-casino leadership."),
  B("Flutter Entertainment","FLUT","strat",50,"Operator vertically integrating its highest-margin live-casino supply."),
  B("Playtech","PTEC.L","strat",46,"B2B gaming-tech peer; a content and distribution combination."),
 ],
 "CYBR": [
  B("Palo Alto Networks","PANW","strat",95,"Announced an agreement to acquire CyberArk for ~$25bn ($45.00 cash + 2.2005 PANW shares per share); identity is the platform's next pillar. A deal is on the table, not a hypothesis."),
  B("Cisco","CSCO","strat",46,"A theoretical alternative identity buyer, now pre-empted by the PANW agreement."),
  B("CrowdStrike","CRWD","strat",44,"Identity adjacency, also pre-empted by the announced deal."),
  B("Thoma Bravo","","spons",42,"Would have been a natural sponsor, now overtaken by the strategic bid."),
 ],
 "SGE.L": [
  B("Thoma Bravo","","spons",72,"Sage is a large, sticky SMB-accounting franchise; recurring revenue and pricing power suit a software take-private."),
  B("Hg","","spons",64,"European software champion-builder; a natural sponsor for a UK SaaS large-cap."),
  B("Vista Equity Partners","","spons",62,"Operational SaaS sponsor for a margin-expansion play."),
  B("Intuit","INTU","strat",58,"Global SMB-accounting leader; a Sage combination is the obvious strategic consolidation, subject to antitrust."),
  B("Microsoft","MSFT","strat",46,"Could fold SMB financials into Dynamics, though large and antitrust-sensitive."),
 ],
 "NICE": [
  B("Thoma Bravo","","spons",70,"Large CX / contact-centre plus compliance franchise with recurring revenue; a fit for a big software take-private after its de-rating."),
  B("Vista Equity Partners","","spons",64,"CX / CCaaS operational sponsor."),
  B("Salesforce","CRM","strat",58,"Front-office platform that could fold cloud contact-centre into Service Cloud."),
  B("ServiceNow","NOW","strat",54,"Workflow platform extending into customer / agent workflows and CX analytics."),
  B("SAP","SAP.DE","strat",44,"CX adjacency to its enterprise suite."),
 ],
 "SINCH.ST": [
  B("Thoma Bravo","","spons",64,"Messaging / CPaaS infrastructure with recurring revenue suits a take-private and deleveraging."),
  B("EQT","","spons",60,"Nordic sponsor able to take a de-rated, founder-influenced CPaaS leader private."),
  B("Twilio","TWLO","strat",58,"CPaaS peer; a combination would consolidate messaging scale and route economics."),
  B("Cisco","CSCO","strat",46,"Communications-software consolidator (Webex) extending into CPaaS."),
  B("Ericsson","ERIC-B.ST","strat",44,"Network-API ambitions could absorb CPaaS messaging assets."),
 ],
 "NOD.OL": [
  B("Qualcomm","QCOM","strat",62,"Connectivity / IoT consolidator seeking low-power short-range wireless leadership."),
  B("STMicroelectronics","STM","strat",58,"Wireless / MCU adjacency for IoT."),
  B("Infineon","IFX.DE","strat",56,"Connectivity / IoT IP complements its microcontroller and security portfolio."),
  B("Niche-IP sponsor","","spons",50,"A fabless-IP sponsor play on a low-power wireless leader."),
  B("Nordic itself is an acquirer","","strat",36,"Nordic also buys (Memfault); as a target it offers scarce ultra-low-power BLE IP."),
 ],
 "CHKP": [
  B("Thoma Bravo","","spons",58,"Cash-rich, profitable security franchise; a classic take-private, though founder / anchor influence is a gate."),
  B("Cisco","CSCO","strat",56,"Network-security consolidator that could absorb a firewall / threat-prevention leader."),
  B("Broadcom","AVGO","strat",54,"Cash-flow-focused infrastructure-software acquirer."),
  B("Palo Alto Networks","PANW","strat",50,"Platform consolidator, though product overlap creates antitrust questions."),
  B("Zscaler","ZS","strat",42,"Zero-trust peer seeking gateway / firewall breadth."),
 ],
 "S": [
  B("Thoma Bravo","","spons",58,"AI-native endpoint platform with strong ARR growth; a take-private once growth-stock sentiment / valuation reset."),
  B("Cisco","CSCO","strat",56,"Endpoint / XDR would complement Splunk-era SecOps ambitions."),
  B("Palo Alto Networks","PANW","strat",48,"Endpoint adjacency, though it overlaps Cortex."),
  B("CrowdStrike","CRWD","strat",40,"Direct peer; strategically logical but competitively fraught."),
  B("Microsoft / Google","MSFT","strat",40,"Hyperscalers extending native security, antitrust-sensitive."),
 ],
}

# ---------------------------------------------------------------------------
# 4. STRUCTURED THESIS  --  what is scarce, the likely path, the key risk
# ---------------------------------------------------------------------------
ASSET_BY_SUB = {
 "pay":    "licensed, pan-European merchant-acquiring scale and recurring transaction volumes - assets that are slow and expensive to build organically",
 "gaming": "owned AAA / franchise IP and studio capacity - scarce, hard to replicate and strategically coveted by platform owners",
 "itserv": "nearshore / onshore delivery capacity, regulated-industry client relationships and AI-transformation skills",
 "semis":  "process and product IP (RF, power, sensing) that is strategically pivotal amid reshoring and the EU Chips Act",
 "semieq": "specialised metrology / inspection / process tooling that anchors customer roadmaps - a structural choke-point in the supply chain",
 "appsw":  "sticky, mission-critical software with high recurring revenue and switching costs",
 "infrasw":"infrastructure-grade software embedded in customer operations, with durable recurring revenue",
 "cyber":  "a defensible security niche with a blue-chip (often government) customer base in a market that consolidates around platforms",
 "internet":"category leadership, proprietary data and a hard-to-replicate audience / network effect",
 "hw":     "engineered hardware / sensing IP and an installed base with aftermarket pull-through",
}
PATH_PRECEDENT = {
 "pay":    "European payments has consolidated relentlessly around a handful of champions and sponsor take-privates",
 "gaming": "with sponsors funding the bulk of 2025 gaming M&A and platform owners chasing IP",
 "itserv": "mid-cap IT-services are routinely absorbed by the majors or rolled up by sponsors",
 "semis":  "semis consolidation is driven by reshoring, scale economics and strategic-asset policy",
 "semieq": "wafer-fab-equipment consolidates around tool breadth and roadmap control",
 "appsw":  "software take-privates are the single most active sponsor strategy, with Europe a 2025-26 focus",
 "infrasw":"infrastructure software is a core sponsor and strategic roll-up category",
 "cyber":  "security buyers consolidate point leaders into platforms, with sponsors equally active",
 "internet":"profitable internet and classifieds platforms have repeatedly gone to sponsor consortia",
 "hw":     "industrial-tech and networking hardware consolidate via both strategics and carve-out sponsors",
}

# Bespoke thesis text for top names. Any of asset/path/risk supplied here
# overrides the computed version; why_now stays computed so its NUMBERS refresh.
THESIS_OVERRIDE = {
 "TEMN.SW": {"asset":"Temenos's appeal is the T24 / Transact core-banking platform - mission-critical software embedded in hundreds of banks, with very high switching costs and recurring maintenance.",
   "path":"The most probable route is a sponsor-led take-private: Temenos has been in early-stage talks with Thoma Bravo and is also linked to EQT, with Goldman Sachs and Citi mandated to test a sale amid activist (Petrus Advisers) pressure.",
   "risk":"Key obstacle: a full take-private of a CHF-listed large-cap is a sizeable cheque, and prior accounting / leadership scrutiny raises diligence intensity."},
 "WLN.PA": {"asset":"Worldline's appeal is pan-European merchant-acquiring scale and licensed transaction rails - strategically valuable assets trapped inside a broken share price (down ~90% from its 2021 peak).",
   "path":"The most probable route is a sponsor-led take-private, most likely of selected parts: a buyer carves out the high-quality merchant-services arm and leaves weaker units behind. A Nexi merger is the strategic alternative but faces French / Italian political resistance.",
   "risk":"Key obstacle: the factors that depressed the stock (terminal-value doubts, merchant-risk losses) complicate diligence, and politics blocks the cleanest strategic combination."},
 "UBI.PA": {"asset":"Ubisoft's appeal is owned AAA franchise IP - Assassin's Creed, Far Cry, Rainbow Six - now ring-fenced in the Tencent-backed Vantage Studios vehicle (valued at ~EUR 3.8bn pre-money).",
   "path":"The most probable route is a Tencent escalation from minority to control, or a family-plus-sponsor take-private; an outright third-party bid is less likely given Tencent's entrenched position and French sensitivities.",
   "risk":"Key obstacle: Tencent's existing stakes effectively gate any rival bid, and France treats marquee IP as a strategic asset."},
 "DAVA": {"asset":"Endava's appeal is scarce nearshore digital-engineering capacity (Central / Eastern Europe, LatAm) serving blue-chip enterprise clients - capability the majors routinely buy rather than build.",
   "path":"The most probable route is a strategic tuck-in by a services major (Accenture, Capgemini) or a peer merger with EPAM; a sponsor take-private is the financial alternative after the de-rating.",
   "risk":"Key obstacle: a founder-influenced / dual-class structure and a still-premium services multiple can deter a clean bid."},
 "AMS.SW": {"asset":"ams-OSRAM's appeal is automotive and industrial optical-sensing / photonics IP - but the equity case hinges on margin recovery; analysts link a takeover to reaching ~15% adjusted EBITDA by 2026.",
   "path":"The most probable route is either an industrial-strategic acquisition once margins recover, or a sponsor-led break-up; the >90% free float leaves the register fully open.",
   "risk":"Key obstacle: leverage and an unfinished turnaround keep buyers cautious until profitability targets are demonstrably hit."},
 "ATO.PA": {"asset":"Atos's appeal is selective: sovereign-critical supercomputing and cybersecurity (Eviden / BDS), set against a heavily restructured balance sheet and legacy managed-infrastructure liabilities.",
   "path":"The most probable control change is via the financial restructuring itself - creditors converting to equity - alongside a state-backed ring-fencing of the sovereign-defence unit; clean strategic M&A of the whole is unlikely.",
   "risk":"Key obstacle: balance-sheet complexity and sovereignty constraints mean buyers want only the crown jewels, not the whole."},
 "NEXI.MI": {"asset":"Nexi's appeal is the largest pan-European merchant-acquiring and digital-payments estate (built via SIA and Nets) - recurring volumes and distribution at scale.",
   "path":"The most probable route is a sponsor-led take-private by its heritage backers; Italy has been reported to favour keeping Nexi independent over a Worldline tie-up.",
   "risk":"Key obstacle: enterprise value and political sensitivity to foreign control of national payment rails."},
 "ALLFG.AS": {"asset":"Allfunds's appeal is a dominant European fund-distribution network (a B2B wealthtech 'rail') plus the data that rides on it - a hard-to-replicate network effect.",
   "path":"The most probable route is either a strategic bid from market-infrastructure (Euronext approached in 2023) or a sponsor take-private backed by existing holders.",
   "risk":"Key obstacle: major shareholders must align on price - a prior Euronext approach lapsed on valuation."},
 "EVO.ST": {"asset":"Evolution's appeal is a dominant, extremely cash-generative live-casino studio network with structural margins - scarce B2B gaming infrastructure.",
   "path":"The most probable route is a sponsor take-private after the valuation reset, though founder influence and grey-market scrutiny narrow the strategic field.",
   "risk":"Key obstacle: regulatory / AML scrutiny of grey-market revenue and a founder-influenced register temper bidder appetite."},
 "CYBR": {"asset":"CyberArk's appeal is identity and privileged-access security leadership - the pillar large platforms most want to own.",
   "path":"Path resolved: Palo Alto Networks has agreed to acquire CyberArk for ~$25bn (announced 2025). The open question is regulatory close, not whether a buyer exists.",
   "risk":"Key risk now is deal completion (antitrust and closing conditions) rather than sourcing a bidder."},
 "SGE.L": {"asset":"Sage's appeal is a vast installed base of SMB accounting / payroll customers with high switching costs and a cloud-subscription transition still running.",
   "path":"The most probable route is a software take-private (Sage's scale and recurring revenue fit the largest sponsors) or a strategic combination with Intuit, antitrust permitting.",
   "risk":"Key obstacle: size and a still-premium SaaS multiple; antitrust would scrutinise any Intuit tie-up."},
 "NICE": {"asset":"NICE's appeal is leadership in cloud contact-centre (CXone) plus financial-crime / compliance software - recurring, mission-critical enterprise platforms.",
   "path":"The most probable route is a large software take-private after the AI-driven de-rating, with strategic CX platforms (Salesforce, ServiceNow) the alternative.",
   "risk":"Key obstacle: enterprise value and the market's AI-disruption worry on contact-centre seats - buyers will want conviction on the AI transition."},
 "SINCH.ST": {"asset":"Sinch's appeal is global A2P messaging scale and direct carrier connections - infrastructure with recurring enterprise volumes.",
   "path":"The most probable route is a sponsor take-private (a deleveraging story) or CPaaS consolidation with a peer such as Twilio.",
   "risk":"Key obstacle: net debt and messaging-margin pressure raise diligence intensity; founders and anchor holders must align."},
 "NOD.OL": {"asset":"Nordic's appeal is a scarce, leading low-power short-range wireless (Bluetooth LE) franchise - fabless, IP-rich and strategically relevant to IoT consolidators.",
   "path":"The most probable route is a strategic acquisition by a connectivity / IoT major (Qualcomm, ST, Infineon) seeking low-power wireless IP.",
   "risk":"Key obstacle: a premium fabless multiple and Norwegian strategic-asset sensitivity."},
 "CHKP": {"asset":"Check Point's appeal is a highly profitable, cash-rich network-security franchise with a large enterprise installed base.",
   "path":"The most probable route is a sponsor take-private or a network-security consolidation; the founder's influence and the cash pile shape any deal.",
   "risk":"Key obstacle: founder / management control and a premium for quality; limited urgency to sell."},
 "S": {"asset":"SentinelOne's appeal is an AI-native endpoint / XDR platform with strong ARR growth - a scaled alternative to CrowdStrike.",
   "path":"The most probable route is a strategic acquisition by a platform seeking endpoint (Cisco), or a sponsor take-private if growth-stock sentiment stays weak.",
   "risk":"Key obstacle: a still-elevated growth multiple and founder / board control; competitive overlap complicates some strategics."},
}

# ---- number formatters (graceful with missing data) ----
def _mc(eur):
    if not eur: return None
    bn = eur/1e9
    return ("EUR %.1fbn" % bn) if bn < 100 else ("EUR %.0fbn" % bn)

def _ev(x):
    if x is None or x <= 0 or x > 100: return None
    return "%.0fx EV/EBITDA" % x

def _bs(nd):
    if nd is None: return (None, "na")
    if nd < 0:   return ("a net-cash balance sheet", "clean")
    if nd < 2:   return ("modest leverage (%.1fx net debt/EBITDA)" % nd, "ok")
    return ("elevated leverage (%.1fx net debt/EBITDA)" % nd, "lev")

def _float(fp):
    if fp is None: return (None, "na")
    pct = min(fp, 1.0) * 100
    if pct >= 70: return ("a high free float (~%.0f%%)" % pct, "open")
    if pct >= 40: return ("a moderate free float (~%.0f%%)" % pct, "mid")
    return ("a concentrated register (only ~%.0f%% free)" % pct, "tight")

def _why_now(rec):
    F, R, name = rec["factors"], rec["raw"], rec["name"]
    val = F.get("f_val") or 50
    vp = "screens cheap against its peer set" if val >= 70 else \
         ("trades broadly in line with peers" if val >= 45 else "screens richly valued versus peers")
    mc, ev = _mc(R.get("mktcap_eur")), _ev(R.get("ev_ebitda"))
    if mc and ev:  head = "At %s and %s, %s %s" % (mc, ev, name, vp)
    elif mc:       head = "At %s, %s %s" % (mc, name, vp)
    else:          head = "%s %s" % (name, vp)
    bsP, bsK = _bs(R.get("nd_ebitda"))
    flP, flK = _float(R.get("float_pct"))
    s = head + "."
    tail = [p for p in (bsP, flP) if p]
    if tail:
        fin = "an acquirer could finance a bid cleanly" if bsK in ("clean", "ok") else "a buyer would need to refinance debt"
        if flK == "tight":
            fin = "the controlled register is the principal obstacle to a clean bid"
        s += " With %s, %s." % (" and ".join(tail), fin)
    flags = (rec.get("edgar") or {}).get("si_flags") or []
    if flags:
        s += " <b>Live signal:</b> " + ("; ".join(str(x) for x in flags))[:170] + "."
    return s

def _asset(rec):
    ov = THESIS_OVERRIDE.get(rec["ticker"], {})
    if ov.get("asset"): return ov["asset"]
    base = ASSET_BY_SUB.get(rec["subsector"], ASSET_BY_SUB["appsw"])
    sc = (rec.get("edgar") or {}).get("sc_deals")
    extra = (" Sector consolidation is live (%d related deals filed in the trailing 24 months)." % sc) if (sc and sc >= 3) else ""
    return "%s's core appeal is %s.%s" % (rec["name"], base, extra)

def _path(rec, buyers):
    ov = THESIS_OVERRIDE.get(rec["ticker"], {})
    if ov.get("path"): return ov["path"]
    prec = PATH_PRECEDENT.get(rec["subsector"], "")
    if not buyers:
        return "The most probable route is a strategic combination." + ((" " + prec[0].upper() + prec[1:] + ".") if prec else "")
    top = buyers[0]
    if top["t"] == "spons":   lead = "The most probable route is a sponsor-led take-private (lead candidate %s)" % top["n"]
    elif top["t"] == "state": lead = "The most probable route is a sovereign-anchored acquisition (lead candidate %s)" % top["n"]
    else:                     lead = "The most probable route is a strategic combination, with %s the lead candidate" % top["n"]
    return lead + ((", as " + prec + ".") if prec else ".")

def _risk(rec):
    ov = THESIS_OVERRIDE.get(rec["ticker"], {})
    if ov.get("risk"): return ov["risk"]
    F, R, sub = rec["factors"], rec["raw"], rec["subsector"]
    fl = R.get("float_pct")
    if fl is not None and min(fl, 1.0) < 0.4:
        return "Key obstacle: a concentrated / founder-influenced register - any deal needs the core holders onside."
    if (F.get("f_sz") or 50) < 25:
        return "Key obstacle: scale - at this size the pool of able acquirers is small and a deal would be transformational for the buyer."
    if sub in ("semis", "semieq", "pay", "hw", "cyber"):
        return "Key obstacle: regulatory and strategic-asset review (antitrust, FDI / sovereignty) can slow or block a cross-border bid."
    nd = R.get("nd_ebitda")
    if nd is not None and nd >= 2.5:
        return "Key obstacle: balance-sheet leverage raises the equity cheque and narrows the buyer pool."
    return "Key obstacle: price expectations - a board would demand a full premium given the asset's scarcity."

# ---------------------------------------------------------------------------
# 5. PUBLIC ENTRY POINT  --  called by pipeline.py for each company
# ---------------------------------------------------------------------------
def rank_buyers(rec, top=6):
    F = rec.get("factors") or {}
    cands, seen = [], set()
    self_n, self_t = rec.get("name"), rec.get("ticker")
    def _is_self(b):
        return b["n"] == self_n or (b["tk"] and b["tk"] == self_t)
    for b in NAMED_BUYERS.get(rec["ticker"], []):
        if _is_self(b) or b["n"] in seen:
            continue
        cands.append(b); seen.add(b["n"])
    for b in SUBSECTOR_BUYERS.get(rec["subsector"], SUBSECTOR_BUYERS["appsw"]):
        if _is_self(b) or b["n"] in seen:
            continue
        cands.append(b); seen.add(b["n"])
    out = [{"n": b["n"], "tk": b["tk"], "t": b["t"], "fit": adj_fit(b["base"], b["t"], F), "why": b["why"]}
           for b in cands]
    out.sort(key=lambda x: -x["fit"])
    return out[:top]

def enrich(rec):
    """rec must have: name, ticker, subsector, factors{f_*}, raw{...}, edgar{...}.
       Returns {'buyers':[...], 'thesis':{why_now,asset,path,risk}}."""
    rec.setdefault("factors", {})
    rec.setdefault("raw", {})
    rec.setdefault("edgar", {})
    buyers = rank_buyers(rec)
    thesis = {"why_now": _why_now(rec), "asset": _asset(rec),
              "path": _path(rec, buyers), "risk": _risk(rec)}
    return {"buyers": buyers, "thesis": thesis}
