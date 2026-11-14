from interview_api.ai import get_ai
from interview_api.ai.mock import MockInterviewAI
from interview_api.ai.schemas import AnswerAssessment
from interview_api.main import app

from .conftest import answer, new_interview


class Improving(MockInterviewAI):
    """Each assessment scores one point higher than the last, so trends are predictable."""

    def __init__(self):
        self.n = 3

    def assess_answer(self, ctx, transcript):
        self.n += 1
        s = min(self.n, 10)
        return AnswerAssessment(
            relevance=s,
            correctness=s,
            depth=s,
            structure=s,
            clarity=s,
            summary="ok",
            strengths=["a"],
            improvements=["b"],
            clarity_feedback="c",
            example_answer="d",
        )


def _complete(client, role, n_answers):
    iv = new_interview(client, role=role, n=3)
    for i in range(n_answers):
        assert answer(client, iv, i).status_code == 200
    return client.post(f"/api/interviews/{iv['id']}/complete").json()


def test_progress_trends_by_role_and_skill(client, user):
    ai = Improving()
    app.dependency_overrides[get_ai] = lambda: ai
    first = _complete(client, "Data Analyst", 3)  # rubric 4,5,6
    _complete(client, "Product Manager", 1)  # rubric 7
    last = _complete(client, "Data Analyst", 3)  # rubric 8,9,10
    new_interview(client, role="Data Analyst")  # in progress: not in progress stats

    all_roles = client.get("/api/progress").json()
    assert len(all_roles["points"]) == 3
    assert all_roles["roles_practised"] == ["Data Analyst", "Product Manager"]
    by_role = {r["role"]: r for r in all_roles["by_role"]}
    assert by_role["Data Analyst"]["interviews"] == 2
    assert by_role["Data Analyst"]["latest_overall"] == last["overall_score"]

    da = client.get("/api/progress", params={"role": "Data Analyst"}).json()
    pts = da["points"]
    assert [p["interview_id"] for p in pts] == [first["id"], last["id"]]
    assert pts[0]["relevance"] == 50.0 and pts[1]["relevance"] == 90.0  # mean 5 / 9, x10
    skills = {s["skill"]: s for s in da["skills"]}
    assert skills["Relevance"]["change"] == 40.0
    assert skills["Overall"]["first"] == first["overall_score"]
    assert skills["Overall"]["latest"] == last["overall_score"]
    assert skills["Behavioural questions"]["latest"] is not None
    assert skills["Technical questions"]["latest"] is not None
    assert da["question_skills"] and all(q["answers"] >= 1 for q in da["question_skills"])
    assert pts[1]["wpm"] > 0 and pts[1]["fillers_per_100"] > 0


def test_progress_unknown_role_is_422(client, user):
    assert client.get("/api/progress", params={"role": "Pilot"}).status_code == 422


def test_progress_empty(client, user):
    p = client.get("/api/progress").json()
    assert p["points"] == [] and all(s["latest"] is None for s in p["skills"])
