from pathlib import Path

path = Path('src/interfaces/api/routes/workflows.py')
data = path.read_bytes()
needle = b"prompt = f\"\"\""
start = data.find(needle)
end = data.find(b"\"\"\"", start + len(needle)) + 3
snippet = data[start:end]
Path('snippet.py').write_bytes(snippet)
