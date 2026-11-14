"""The fixed job roles and levels users can pick. A fixed list keeps progress comparable over time
and keeps free text out of the question-generation prompt."""

ROLES: list[str] = [
    "Software Engineer",
    "Frontend Developer",
    "Backend Developer",
    "Data Analyst",
    "Data Scientist",
    "Machine Learning Engineer",
    "DevOps Engineer",
    "Product Manager",
]

LEVELS: list[str] = ["Intern", "Junior", "Mid", "Senior"]
