# Railway / Heroku-style process definitions.
#
# The MAIN app (learner portal + admin) is the Streamlit web process. Railway injects $PORT.
web: streamlit run app.py --server.port $PORT --server.address 0.0.0.0 --server.headless true
#
# The OPTIONAL LTI 1.3 + H5P/xAPI companion is a SEPARATE Railway service (it needs its own HTTP
# port). Deploy it as a second service in the same project, sharing the same DATABASE_URL, with the
# start command:
#   uvicorn companion.lti_app:app --host 0.0.0.0 --port $PORT
companion: uvicorn companion.lti_app:app --host 0.0.0.0 --port $PORT
