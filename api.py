from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from google import genai
from google.genai import types
from dotenv import load_dotenv
import os
import io
from pydantic import BaseModel
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
import tempfile
import json_repair

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://coverup.noobscience.in",
        "https://noobscience.in",
        "http://coverup.noobscience.in",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

client = genai.Client(api_key=os.getenv("GOOGLE_API_KEY"))


def parse_resume(content):
    system_instruction = """
    You are a resume parser. You will be given a resume in PDF format. Your job is to extract the relevant information from the resume and return it in JSON format.
    Follow this JSON schema:
    {
  "other": "{"Hobbies":"","Languages":""}",
  "first_name": "first_name",
  "last_name": "last_name",
  "email": "email",
  "phone": "phone",
  "social": {
    "link_name1": "link_url1",
    "link_name2": "link_url2",
    "link_name3": "link_url3",
  },
  "summary": "summary in the resume",
  "skills": "comma separated list of skills",
  "work": "[{"id": "generate a random id","company":"company","title":"title","startDate":"start_date","endDate":"end_date","description":"description"}]",
  "education": "[{"id": "generate a random id","degree":"degree","institution":"institution","startDate":"start_date","endDate":"end_date"}]",
  "projects": "[{"id": "generate a random id","name":"name","description":"description"}]",
  "achievements": "[{"id": "generate a random id","name":"name","description":"description"}]",
}
    """
    file = types.Part.from_bytes(data=content, mime_type="application/pdf")

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=["Parse the resume", file],
        config=types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=1,
            response_mime_type="application/json",
        ),
    )
    res = response.candidates[0].content.parts[0].text
    return res


@app.post("/parse")
async def parse_pdf(file: UploadFile = File(...)) -> dict:
    if file.content_type not in [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "text/plain",
    ]:
        raise HTTPException(
            status_code=400, detail="File must be a PDF, docx or text file"
        )

    try:
        res = {}
        file_content = file.file.read()
        parsed_data = parse_resume(file_content)
        res = json_repair.loads(parsed_data, logging=True)
        res["other"] = json_repair.loads(res["other"])
        res["work"] = json_repair.loads(res["work"])
        res["education"] = json_repair.loads(res["education"])
        res["projects"] = json_repair.loads(res["projects"])
        res["achievements"] = json_repair.loads(res["achievements"])

        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing PDF: {str(e)}")


class CreateLetterRequest(BaseModel):
    text: str


@app.post("/create")
async def create_cover_letter(request: CreateLetterRequest):
    try:
        buffer = io.BytesIO()

        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=72,
            leftMargin=72,
            topMargin=72,
            bottomMargin=72,
        )

        styles = getSampleStyleSheet()
        custom_style = ParagraphStyle(
            "CustomStyle",
            parent=styles["Normal"],
            fontSize=12,
            leading=14,
            spaceBefore=12,
            spaceAfter=12,
        )

        elements = []
        paragraph = Paragraph(request.text.replace("\n", "<br/>"), custom_style)
        elements.append(paragraph)

        doc.build(elements)

        buffer.seek(0)

        with tempfile.NamedTemporaryFile() as temp_file_path:
            temp_file_path.write(buffer.getvalue())

            print("done")

            return Response(
                content=buffer.getvalue(),
                media_type="application/pdf",
            )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating PDF: {str(e)}")
