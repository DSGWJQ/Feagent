from pathlib import Path
path = Path('src/interfaces/api/routes/workflows.py')
data = path.read_bytes()
needle = b'            raise ValueError('
start = data.index(needle)
end = data.find(b"\n", start)
old_line = data[start:end]
print(old_line)
