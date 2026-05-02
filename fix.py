from backend.services.resume_builder import _json_to_markdown, _md_to_pdf
import json

sample = {
    "resume": {
        "fullName": "Syed Mawahid Hussain",
        "professionalSummary": "Strong CS student with Python skills.",
        "technicalSkills": {
            "languages": ["Python", "Java", "C++"],
            "frameworks": ["React", "FastAPI"]
        },
        "projects": [
            {
                "name": "RAG Chatbot",
                "description": "Built chatbot using OpenAI API"
            },
            {
                "name": "Voice Emotion Recognition",
                "description": "Python + React project"
            }
        ]
    }
}

md = _json_to_markdown(sample)
print(md)

pdf = _md_to_pdf(md)

with open("resume.pdf", "wb") as f:
    f.write(pdf)

print("done")