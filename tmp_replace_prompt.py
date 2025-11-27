from pathlib import Path

path = Path('src/interfaces/api/routes/workflows.py')
data = path.read_bytes()
marker = b"        prompt = f\"\"\""
start = data.index(marker)
after_marker = start + len(marker)
end = data.index(b"\"\"\"", after_marker)
english = """You are a workflow designer. Based on the following requirements, create a JSON workflow specification.\n\nRequirements:\n- Description: {description}\n- Goal: {goal}\n\nThe JSON must include:\n{{\n  \"name\": \"Workflow name\",\n  \"description\": \"Workflow description\",\n  \"nodes\": [\n    {{\n      \"type\": \"start|end|httpRequest|textModel|database|conditional|loop|python|transform|file|notification\",\n      \"name\": \"Node name\",\n      \"config\": {{}} ,\n      \"position\": {{\"x\": 100, \"y\": 100}}\n    }}\n  ],\n  \"edges\": [\n    {{\"source\": \"node_1\", \"target\": \"node_2\"}}\n  ]\n}}\n\nRules:\n1. Include at least one start node and one end node.\n2. Node types must be selected from the supported list.\n3. Edge source/target must reference existing nodes.\n4. Return valid JSON only, without extra commentary.\n"""
new_block = marker + b"\n" + english.encode('utf-8') + b"\n"
new_data = data[:start] + new_block + data[end+3:]
path.write_bytes(new_data)
