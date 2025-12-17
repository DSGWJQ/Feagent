prompt = """
You are a workflow designer. Based on the following description and goal, create a JSON workflow specification.

Description: {description}
Goal: {goal}

The JSON must include:
{
  "name": "Workflow name",
  "description": "Workflow description",
  "nodes": [
    {
      "type": "start|end|httpRequest|textModel|database|conditional|loop|python|transform|file|notification",
      "name": "Node name",
      "config": {},
      "position": {"x": 100, "y": 100}
    }
  ],
  "edges": [
    {"source": "node_1", "target": "node_2"}
  ]
}

Rules:
1. Include at least one start node and one end node.
2. Node types must be from the supported list.
3. Edge source/target must reference existing nodes.
4. Return valid JSON only without extra commentary.
"""
