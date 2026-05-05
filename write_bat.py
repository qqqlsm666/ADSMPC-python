import io
content = (
    "@echo off\r\n"
    'call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat"\r\n'
    "set FORCE_CPU=1\r\n"
    "set DISTUTILS_USE_SDK=1\r\n"
    "D:\r\n"
    'cd "D:\\桌面\\加密rag\\ADSMPC-python\\NssMPClib\\csprng"\r\n'
    "D:\\anaconda\\envs\\ADSMPC-python\\python.exe setup.py clean\r\n"
    "D:\\anaconda\\envs\\ADSMPC-python\\Scripts\\pip.exe install -e . --no-build-isolation\r\n"
)
with open(r'D:/桌面/加密rag/ADSMPC-python/NssMPClib/csprng/build_cpu.bat', 'wb') as f:
    f.write(content.encode('gbk'))
print('written')
