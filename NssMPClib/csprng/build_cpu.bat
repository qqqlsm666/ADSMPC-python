@echo off
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat"
set FORCE_CPU=1
set DISTUTILS_USE_SDK=1
D:
cd "D:\◊¿√Ê\º”√‹rag\ADSMPC-python\NssMPClib\csprng"
D:\anaconda\envs\ADSMPC-python\python.exe setup.py clean
D:\anaconda\envs\ADSMPC-python\Scripts\pip.exe install -e . --no-build-isolation
