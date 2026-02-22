# agents.py

agents = {
    "Agent1": {
        "skills": {"Technical": 0.9, "Billing": 0.1, "Legal": 0.0},
        "capacity": 5,
        "load": 0
    },
    "Agent2": {
        "skills": {"Billing": 0.8, "Legal": 0.2, "Technical": 0.2},
        "capacity": 4,
        "load": 0
    }
}

def select_agent(category):
    best_agent = None
    best_score = -1

    for name, data in agents.items():
        if data["load"] >= data["capacity"]:
            continue

        skill_match = data["skills"].get(category, 0)
        availability = 1 - (data["load"] / data["capacity"])

        score = 0.6 * skill_match + 0.4 * availability

        if score > best_score:
            best_score = score
            best_agent = name

    return best_agent