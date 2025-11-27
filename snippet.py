prompt = f"""
浣犳槸涓€涓伐浣滄祦璁捐甯堛€傛牴鎹互涓嬮渶姹傦紝鐢熸垚涓€涓?JSON 鏍煎紡鐨勫伐浣滄祦缁撴瀯銆?
闇€姹傦細
- 鎻忚堪锛歿description}
- 鐩爣锛歿goal}

鐢熸垚鐨?JSON 蹇呴』鍖呭惈浠ヤ笅瀛楁锛?{{
  "name": "宸ヤ綔娴佸悕绉?,
  "description": "宸ヤ綔娴佹弿杩?,
  "nodes": [
    {{
      "type": "start|end|httpRequest|textModel|database|conditional|loop|python|transform|file|notification",
      "name": "鑺傜偣鍚嶇О",
      "config": {{}},
      "position": {{"x": 100, "y": 100}}
    }}
  ],
  "edges": [
    {{"source": "node_1", "target": "node_2"}}
  ]
}}

瑕佹眰锛?1. 蹇呴』鑷冲皯鏈変竴涓紑濮嬭妭鐐癸紙start锛夊拰涓€涓粨鏉熻妭鐐癸紙end锛?2. 鑺傜偣绫诲瀷蹇呴』浠庢敮鎸佺殑绫诲瀷涓€夋嫨
3. 杈圭殑source鍜宼arget蹇呴』鎸囧悜鏈夋晥鐨勮妭鐐?4. 杩斿洖鏈夋晥鐨?JSON锛屼笉瑕佸寘鍚换浣曞叾浠栨枃鏈?
鏍规嵁杩欎釜闇€姹傜敓鎴愬伐浣滄祦 JSON锛?"""