@echo off
echo Checking Git status...
git status

echo.
echo Adding all files...
git add .

echo.
echo Creating commit...
git commit -m "Add all source files for Vercel deployment"

echo.
echo Ready to push! Run: git push origin main
pause
