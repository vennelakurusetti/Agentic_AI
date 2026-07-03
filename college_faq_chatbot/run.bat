@echo off
REM Run College FAQ Chatbot using system Python 3.12
SET PYTHON=C:\Users\madha\AppData\Local\Programs\Python\Python312\python.exe
SET STREAMLIT=C:\Users\madha\AppData\Local\Programs\Python\Python312\Scripts\streamlit.exe

if "%1"=="ingest" (
    %PYTHON% ingest.py
    goto :eof
)
if "%1"=="app" (
    %PYTHON% -m streamlit run app.py
    goto :eof
)
if "%1"=="evaluate" (
    %PYTHON% evaluator.py
    goto :eof
)

echo Usage: run.bat [ingest^|app^|evaluate]
echo   ingest   - Run document ingestion
echo   app      - Start Streamlit chatbot
echo   evaluate - Run RAGAS evaluation