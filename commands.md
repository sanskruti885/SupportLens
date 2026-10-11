py -3.14 -m venv .venv
.venv\Scripts\activate
python -m pip install pytest
<!-- Test folder ran -->
python -m pytest -v 
<!-- Install fastapi and uvicorn(uvicorn run fastapi application on web server) -->
python -m pip install fastapi uvicorn
<!-- Simulator needs to send request to fastapi -->
python -m pip install requests
<!-- install streamlit for ui -->
python -m pip install streamlit pandas

1. Create db.py
2. Create tests folder add the database testing file
3. Create the api.py
4. test the folder again
5. Run the server
python -m uvicorn api:app --reload

6. Create a simulator.py which will send the request to fastapi
7. run simulator
python simulator.py

8. Created detector.py which containes the rules to check against the metrics
9. Created test_detector.py file in test folder 
python -m pytest -v test/test_detector.py

10. Added disk failure to node 2 
python simulator.py --failure disk --node node-2
11. python detector.py
Check api and open alerts

12. Created summary_generator.py so that icident, evidence and recommendation can be told to user

13. Create ui frontend/app.py
python -m streamlit run frontend/app.py

here
api : file name
app : FastAPI() instance
