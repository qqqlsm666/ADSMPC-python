import io
content = (
    "@echo off\r\n"
    'call "C:\\Program Files\\Microsoft Visual Studio\\2022\\Community\\VC\\Auxiliary\\Build\\vcvars64.bat" >nul\r\n'
    'dumpbin /dependents "D:\\桌面\\加密rag\\ADSMPC-python\\NssMPClib\\csprng\\torchcsprng\\_C.cp310-win_amd64.pyd"\r\n'
)
with open(r'D:/桌面/加密rag/ADSMPC-python/NssMPClib/csprng/dump_deps.bat', 'wb') as f:
    f.write(content.encode('gbk'))
print('written')
