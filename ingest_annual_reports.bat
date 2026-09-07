@echo off
setlocal
cd /d "%~dp0"
echo ============================================================
echo Financial GraphRAG - Offline Annual Report Ingestion
echo ============================================================
echo.
python offline_ingest.py %*
if errorlevel 1 (
  echo.
  echo Ingestion failed. Review the messages above.
  pause
  exit /b %errorlevel%
)
echo.
echo Ingestion completed. Start Streamlit with:
echo   python -m streamlit run app.py
pause
