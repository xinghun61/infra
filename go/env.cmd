@echo off
:: This script bootstrap the go toolset and modifies an environment 
:: of the calling shell to include correct GOPATH, GOBIN and so.
::
:: Unlike env.py, this script can't be used as a wrapping command,
:: use env.py for that (e.g. "python env.py some_script_that_need_go.py").

SET script_path=%~dp0
SET temp_script=%script_path%\_setup_env.cmd

:: This spits out a bunch of 'set VAR=VALUE' commands.
call python %script_path%\env.py > %temp_script%
:: This injects them into shell environment.
call %temp_script%

del %temp_script%

:: To avoid polluting env with crap.
set temp_script=
set script_path=