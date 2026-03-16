import sys
sys.path.append("src")
from diagram_generator import DiagramGenerator

gen = DiagramGenerator()

path1 = gen.save_svg(None, "rag-stack", "Open Source RAG Stack", "Ecosystem Tree")
print("Generated:", path1)

path2 = gen.save_svg(None, "ai-skills-map", "AI Skills & Technologies Map", "Honeycomb Map")
print("Generated:", path2)

path3 = gen.save_svg(None, "llm-vs-agentic", "LLM vs Generative AI vs AI Agents Agentic AI", "Parallel Pipelines")
print("Generated:", path3)

path4 = gen.save_svg(None, "genai-roadmap", "Generative AI Learning Roadmap", "Winding Roadmap")
print("Generated:", path4)
