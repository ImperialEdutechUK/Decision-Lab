"""Development-mode sample learners (no LMS). Guarded by config.DEV_MODE in the UI.
These simulate what an LMS launch would assert; they are NOT a production login."""
SAMPLE_LEARNERS = [
    {"issuer": "dev://local", "external_learner_id": "dev-learner-A", "display_name": "Alex Learner", "email": "alex@example.com"},
    {"issuer": "dev://local", "external_learner_id": "dev-learner-B", "display_name": "Priya Learner", "email": "priya@example.com"},
    {"issuer": "dev://local", "external_learner_id": "dev-learner-C", "display_name": "Sam Learner", "email": "sam@example.com"},
]
