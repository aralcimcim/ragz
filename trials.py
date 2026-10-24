"""Public ClinicalTrials.gov records, normalized for research exploration."""

import re
import time

import requests


API = "https://clinicaltrials.gov/api/v2"
TOPICS = {
    "Alzheimer's disease": "Alzheimer Disease",
    "Parkinson's disease": "Parkinson Disease",
    "Mild cognitive impairment": "Mild Cognitive Impairment",
    "Epilepsy": "Epilepsy",
    "Multiple sclerosis": "Multiple Sclerosis",
    "Stroke": "Stroke",
    "Traumatic brain injury": "Traumatic Brain Injury",
    "Amyotrophic lateral sclerosis": "Amyotrophic Lateral Sclerosis",
    "Huntington's disease": "Huntington Disease",
    "Migraine": "Migraine",
    "Sleep disorders": "Sleep Wake Disorders",
    "ADHD": "Attention Deficit Hyperactivity Disorder",
    "Autism spectrum disorder": "Autism Spectrum Disorder",
}
QUESTIONS = {
    "Study design": "What study types, allocation, masking, phases, and enrollment are described?",
    "Interventions": "What interventions and comparator groups are described in these study protocols?",
    "Primary outcomes": "What primary outcomes are planned, and over what time frames?",
    "Participant criteria": "What participant inclusion and exclusion criteria are stated in these study protocols?",
    "Research overview": "What research questions and study approaches are described in these trial records?",
}


def text(value):
    return str(value).strip() if value is not None else "Not reported"


def normalize(study, topic):
    p = study["protocolSection"]
    identity = p["identificationModule"]
    nct = identity["nctId"]
    if not re.fullmatch(r"NCT\d{8}", nct):
        raise ValueError("Invalid ClinicalTrials.gov identifier.")
    status = p.get("statusModule", {})
    design = p.get("designModule", {})
    info = design.get("designInfo", {})
    eligibility = p.get("eligibilityModule", {})
    description = p.get("descriptionModule", {})
    arms = p.get("armsInterventionsModule", {})
    outcomes = p.get("outcomesModule", {})
    enrollment = design.get("enrollmentInfo", {})
    return {
        "nct_id": nct, "topic": topic, "title": identity.get("briefTitle", nct),
        "url": f"https://clinicaltrials.gov/study/{nct}",
        "status": text(status.get("overallStatus")),
        "last_updated": text(status.get("lastUpdatePostDateStruct", {}).get("date")),
        "study_type": text(design.get("studyType")), "phases": design.get("phases", []),
        "allocation": text(info.get("allocation")),
        "masking": text(info.get("maskingInfo", {}).get("masking")),
        "intervention_model": text(info.get("interventionModel")),
        "enrollment": enrollment.get("count"), "enrollment_type": text(enrollment.get("type")),
        "has_results": bool(study.get("hasResults", False)),
        "conditions": p.get("conditionsModule", {}).get("conditions", []),
        "summary": text(description.get("briefSummary")),
        "interventions": arms.get("interventions", []), "arms": arms.get("armGroups", []),
        "primary_outcomes": outcomes.get("primaryOutcomes", []),
        "eligibility": text(eligibility.get("eligibilityCriteria")),
        "minimum_age": text(eligibility.get("minimumAge")),
        "maximum_age": text(eligibility.get("maximumAge")),
        "sex": text(eligibility.get("sex")),
        "healthy_volunteers": eligibility.get("healthyVolunteers"),
    }


def fetch_trials(topic, limit=30):
    if topic not in TOPICS or not 1 <= limit <= 100:
        raise ValueError("Choose a supported topic and 1–100 trials.")
    trials, raw, seen = [], [], set()
    params = {"query.cond": TOPICS[topic], "pageSize": min(limit, 100),
              "format": "json", "sort": "LastUpdatePostDate:desc"}
    with requests.Session() as session:
        session.headers["User-Agent"] = "TrialTrace public clinical research explorer"
        response = session.get(f"{API}/version", timeout=40)
        response.raise_for_status()
        version = response.json()
        while len(trials) < limit:
            response = session.get(f"{API}/studies", params=params, timeout=40)
            response.raise_for_status()
            data = response.json()
            for study in data.get("studies", []):
                trial = normalize(study, topic)
                if trial["nct_id"] not in seen:
                    trials.append(trial)
                    raw.append(study)
                    seen.add(trial["nct_id"])
                if len(trials) == limit:
                    break
            token = data.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token
            time.sleep(0.2)
    if not trials:
        raise ValueError("No public trial records were returned.")
    return trials, raw, version


def split_text(value, size=1200, overlap=150):
    """Bound passages without changing words; retain a little retrieval context."""
    value = value.strip()
    while value:
        end = min(size, len(value))
        if end < len(value):
            space = value.rfind(" ", size // 2, end)
            if space != -1:
                end = space
        yield value[:end]
        if end == len(value):
            break
        value = value[max(1, end - overlap):].lstrip()


def make_chunks(trial):
    sections = {
        "overview": f"Title: {trial['title']}\nConditions: {', '.join(trial['conditions'])}\nBrief summary: {trial['summary']}",
        "design": (
            f"Study type: {trial['study_type']}\nPhases: {', '.join(trial['phases']) or 'Not reported'}\n"
            f"Allocation: {trial['allocation']}\nMasking: {trial['masking']}\n"
            f"Intervention model: {trial['intervention_model']}\n"
            f"Enrollment: {text(trial['enrollment'])} ({trial['enrollment_type']})\n"
            f"Registry status: {trial['status']}\nLast registry update: {trial['last_updated']}\n"
            f"Results posted flag: {trial['has_results']}"
        ),
        "interventions": "\n".join(
            [f"Intervention: {i.get('name', 'Not reported')} ({i.get('type', 'Not reported')}). {i.get('description', '')}"
             for i in trial["interventions"]] +
            [f"Study arm: {i.get('label', '')} ({i.get('type', '')}). {i.get('description', '')}"
             for i in trial["arms"]]
        ) or "Interventions and study arms: Not reported.",
        "outcomes": "\n".join(
            f"Primary outcome: {i.get('measure', '')}\nTime frame: {i.get('timeFrame', 'Not reported')}\n{i.get('description', '')}"
            for i in trial["primary_outcomes"]
        ) or "Primary outcomes: Not reported.",
        "eligibility": (
            f"Minimum age: {trial['minimum_age']}\nMaximum age: {trial['maximum_age']}\n"
            f"Sex: {trial['sex']}\nHealthy volunteers: {text(trial['healthy_volunteers'])}\n"
            f"Eligibility criteria:\n{trial['eligibility']}"
        ),
    }
    return [{"source_id": f"{trial['nct_id']}:{section}:{part}", "nct_id": trial["nct_id"],
             "section": section, "text": passage, "url": trial["url"], "title": trial["title"],
             "last_updated": trial["last_updated"]}
            for section, content in sections.items() for part, passage in enumerate(split_text(content))]
