@echo off
::PNetNodeBan v3.2
::
:: This batch file looks for nodes that are connected to your pocketnet server and will ban them if:
:: 1. They have a version number that is V0.19.9 or lower
:: 2. They have -1 in Synced_blocks and/or -1 in Synced_headers
:: Old version numbers are buggy and are the highest cause of corrupted block chains and synced_headers/Synced_blocks that are -1
:: have a tendency to suck down lots and lots of data or fill up a slot for a working node. I reccomend running this every hour.
call :settime
set debug=::
:: ^-- debug variable must be set to :: to turn debug off.
set daemonpath=K:\Coins\PocketNet\PocketnetCore\daemon\
set datapath=k:\coins\PocketNet\data\
set logfile=%daemonpath%PNetNodeBan.log
set debuglog=%daemonpath%PNetNodeBan.log
if not exist %logfile% echo Date:%dstr% Time: %tstr% - Starting new log file.>%logfile%
if not exist %debuglog% echo Date:%dstr% Time: %tstr% - Starting new Debug log file.>%debuglog%
if not "%debug%"=="::" echo Debug mode is on. To turn it off then set debug=::>>%debuglog%
%debug%echo Date:%dstr% Time: %tstr% - [debug] %cd%>>%debuglog%
set bantime=604800
:: Ban time is 60*60*24*7
set dot=.
set tt=tt
:: ^-- 2 small variables to stop stupid http parsing
set conf=%datapath%pocketcoin%dot%conf
set pcli-exe=%daemonpath%pocketcoin-cli.exe
set p-cli=%pcli-exe% -conf=%conf%
set jq-exe=k:\utils\jq-win64.exe
 
if not exist %pcli-exe% call :fatal_error 1 %p-cli%
if not exist %jq-exe% call :fatal_error 2 %jq-exe%
call :settime
echo Date: %dstr% Time: %tstr% - Starting PnetNodeBaning script>>%logfile%
%debug%echo Date:%dstr% Time: %tstr% - [debug] Pockenet-cli exe: %p-cli% jq: %jq-exe% Datapath: %datapath% Daemon Path: %daemonpath%>>%debuglog%
%p-cli% getpeerinfo | %jq-exe% -c -r ".[] | \"\(.subver ^| ltrimstr(\"/Satoshi:\") ^| rtrimstr(\"/\") / \".\" ^| \"\(.[0]),\(.[1]),\(.[2])\"),\(.addr /\":\" ^| \"\(.[0])\"),\(.synced_headers),\(.synced_blocks)\"" > %daemonpath%$getpeerinfo$.txt
for /f "tokens=1,2,3,4,5,6 delims=," %%l in (%daemonpath%$getpeerinfo$.txt) do call :checknode %%l %%m %%n %%o %%p %%q
%debug%echo Date:%dstr% Time: %tstr% - [debug] Current path: %cd% >>%debuglog%
%debug%echo Date:%dstr% Time: %tstr% - [debug] program end.>>%debuglog%
if "%debug%"=="::" del %daemonpath%$getpeerinfo$.txt
goto end
:fatal_error
echo Fatal error - %2 can't be found. The path for %2 needs to be valid. Please check that it exists.>>%logfile%
if "%1"=="1" echo Default name is pocketcoin-cli.exe - This exe should be installed in your pocketnet\Daemon\ path under the pocketnet core directories.>>%logfile%
if "%1"=="2" echo Default name is JQ-win64.exe - You can download the windows 64 exe from h%tt%ps://stedolan%dot%github%dot%io/jq/download/>>%logfile%
%debug%echo Date:%dstr% Time: %tstr% - [debug]  Can't find %2>>%debuglog%
echo Fatal error - %2 can't be found. The path for %2 needs to be valid. Please check that it exists.
if "%1"=="1" echo Default name is pocketcoin-cli.exe - This exe should be installed in your pocketnet\Daemon\ path under the pocketnet core directories.
if "%1"=="2" echo Default name is JQ-win64.exe - You can download the windows 64 exe from h%tt%ps://stedolan%dot%github%dot%io/jq/download/
%debug%echo Date:%dstr% Time: %tstr% - [debug]  Can't find %2
goto end
:settime
set d=%date%
set t=%time%
set dstr=%d:~4,2%-%d:~7,2%-%d:~10,4%
set tstr=%t:~0,2%:%t:~3,2%:%t:~6,2%.%t:~9,2%
goto end
:checknode
%debug%echo Date: %dstr% Time: %tstr% - paramaters: %1 %2 %3 %4 %5 %6 %7 %8 %9 %10 %11>>%debuglog%
set bannode=
set banreason=
set full-node-version=v%1.%2.%3
:: ver1 isn't used right now but when a final version/non alpha/beta version is released then we may need this.
set ver1=%1
set ver2=%2
set ver3=%3
set nodeip=%4
set synced-headers=%5
set synced-blocks=%6
:: get the time and date for any log activity that needs to be recorded.
call :settime
 
%debug%echo Date:%dstr% Time: %tstr% - [debug] Node Version: %full-node-version% IP: %node-ip% Synced_blocks: %synced-blocks% Synced_headers: %synced-headers%>>%debuglog%
 
if %synced-headers% LEQ -1 set banreason=Synced-headers less than One.
if %synced-blocks% LEQ -1 set banreason=%banreason% Synced-blocks less than One.
if %ver2% LEQ 18 set ban_reason=%banreason% Node version is less than 19.
if %ver2% GTR 18 if %ver3% LEQ 9 set ban-reason=%banreason% Node version is older than V0.19.6.
%debug%echo Date:%dstr% Time: %tstr% - [debug] Banreason: %banreason%>>%debuglog%
if not "%banreason%"=="" echo Date: %dstr% Time: %tstr% Bad node found: %nodeip% Reason: %banreason%. Banning node for %bantime%>>%logfile%
if not "%banreason%"=="" %p-cli% setban "%nodeip%" add %bantime%>>%logfile%
 
%debug%echo Date: %dstr% Time: %tstr% - [debug] Error level after running ban command: %errorlevel%>>%debuglog%
if %errorlevel%==23 echo Date: %dstr% Time: %tstr% -  Node %nodeip% already banned.>>%logfile%
:end
