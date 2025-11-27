from pathlib import Path

data = Path('src/interfaces/api/routes/workflows.py').read_bytes()
needle = b"prompt = f\"\"\""
start = data.find(needle)
print('start', start)
segment = data[start-20:start+20]
print(segment)
print(list(segment))
