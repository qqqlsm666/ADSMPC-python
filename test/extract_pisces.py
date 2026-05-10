from pypdf import PdfReader

# Pisces - the cryptographic encrypted LLM paper
path = r'D:\桌面\加密rag\ADSMPC-python\doc\17937_Pisces_Cryptography_base.pdf'
reader = PdfReader(path)
out = [f'pages: {len(reader.pages)}']
for i in range(len(reader.pages)):
    out.append(f'\n===== PAGE {i+1} =====')
    text = reader.pages[i].extract_text() or ''
    out.append(text)

with open(r'D:\桌面\加密rag\ADSMPC-python\test\pisces_text.txt', 'w', encoding='utf-8') as f:
    f.write('\n'.join(out))
print('done', len(reader.pages))
