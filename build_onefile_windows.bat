
@echo off
setlocal enabledelayedexpansion
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller
for /f "delims=" %%A in ('python -c "import imageio_ffmpeg as i; print(i.get_ffmpeg_exe())"') do set FFBIN=%%A
if not exist "%FFBIN%" (
  echo Could not locate ffmpeg via imageio-ffmpeg. Aborting.
  exit /b 1
)
pyinstaller --noconfirm --clean --onefile --name ts2mp4 ^
  --add-binary "%FFBIN%;ffbin" ^
  --hidden-import imageio_ffmpeg ^
  app_onefile_progress_fixed2.py
echo Built dist\ts2mp4.exe
endlocal
