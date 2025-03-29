@echo off
echo Running pre-commit checks...
echo If you have not installed pre-commit, please run:
echo pip install pre-commit
echo and then run this script again.

pre-commit run --all-files

pause
