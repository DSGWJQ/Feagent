from pathlib import Path
text = Path('snippet.py').read_text(encoding='utf-8')
idx = text.index('description')
print(hex(ord(text[idx-1])))
print(repr(text[idx-1]))
