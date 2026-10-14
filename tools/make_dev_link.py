"""Print a signed dev launch URL (simulating an LMS signed-token launch) for local testing.

    python -m tools.make_dev_link dev-learner-A "Alex Learner" alex@example.com
"""
import sys

from auth.tokens import mint_launch_token
from config import config


def main():
    sub = sys.argv[1] if len(sys.argv) > 1 else "dev-learner-A"
    name = sys.argv[2] if len(sys.argv) > 2 else "Alex Learner"
    email = sys.argv[3] if len(sys.argv) > 3 else "alex@example.com"
    token = mint_launch_token(sub=sub, name=name, email=email)
    print(f"{config.STREAMLIT_URL}/?launch={token}")


if __name__ == "__main__":
    main()
