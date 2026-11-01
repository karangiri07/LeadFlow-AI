
def calculate_lead_score(name, email, service):

    score = 0

    # Check requested service
    if service.lower() == "ai automation":
        score += 40

    elif service.lower() == "website development":
        score += 30

    # Check email provider
    if email.lower().endswith("@gmail.com"):
        score += 10

    # Check name length
    if len(name.strip()) > 5:
        score += 10

    # Maximum score is 100
    return min(score, 100)


# Automatically calculate lead priority
def calculate_priority(score):

    if score >= 70:
        return "Hot"

    elif score >= 40:
        return "Warm"

    else:
        return "Cold"
