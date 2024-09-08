# import libraries
import os
import time
import base64
import json
import requests
from pydantic import BaseModel
from typing import List, Optional

#
from dotenv import load_dotenv
load_dotenv()


class PDFTable(BaseModel):
    """
    Row as {"column2": "", "column2": ""}
    """
    rows: List[dict] = []

class PDFPageSection(BaseModel):
    path: str = None
    heading: str = None
    paragraphs: List[str] = []
    subSections: Optional[List['PDFPageSection']] = []
    table: Optional[List[PDFTable]] = []

class PDFPage(BaseModel):
    sections: List[PDFPageSection] = []


def parse_paragraph(section, paragraph) -> str:
    role = paragraph.get("role")
    content = paragraph.get("content")
    print(f'paragraph role: {role}')
    if role == "sectionHeading":
        section.heading = content
        return None
    elif role == "footnote":
        return role
    elif role == "pageFooter":
        return role
    elif role == "pageHeader":
        return role
    elif role == "pageNumber":
        return None
    else:
        section.paragraphs.append(content)
        return None

def parse_notes(section, paragraph) -> None:
    content = paragraph.get("content")
    section.paragraphs.append(content)


def submit_pdf(filepath) -> str:
    with open(filepath, "rb") as f:
        base64_encoded_pdf = base64.b64encode(f.read()).decode("utf-8")
    #
    endpoint = os.getenv("ENDPOINT")
    key = os.getenv("KEY")
    modelId = "prebuilt-layout"
    print(f"{endpoint}, {key}")
    #
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": key
    }
    #
    data = {
        "base64Source": base64_encoded_pdf
    }
    # Send a POST request to the API
    # POST {endpoint}/documentintelligence/documentModels/{modelId}:analyze?_overload=analyzeDocument&api-version=2024-07-31-preview&pages={pages}&locale={locale}&stringIndexType={stringIndexType}&features={features}&queryFields={queryFields}&outputContentFormat={outputContentFormat}&output={output}
    url = f"{endpoint}/documentintelligence/documentModels/{modelId}:analyze?api-version=2024-07-31-preview&pages=1"
    response = requests.post(url, headers=headers, json=data)

    # Check if the request was successful
    if response.status_code == 202:
        # Get the operation ID from the response headers
        operation_id = response.headers["apim-request-id"]
        print(f"Operation ID: {operation_id}")
        return operation_id
    else:
        print(f"Error: {response.status_code} - {response.text}")
        return None

def get_result(operationId):
    endpoint = os.getenv("ENDPOINT")
    endpoint = os.getenv("ENDPOINT")
    key = os.getenv("KEY")
    modelId = "prebuilt-layout"
    print(f"{endpoint}, {key}")
    #
    headers = {
        "Content-Type": "application/json",
        "Ocp-Apim-Subscription-Key": key
    }
    # Send a GET request to the API
    url = f"{endpoint}/documentintelligence/documentModels/{modelId}/analyzeResults/{operationId}?api-version=2024-07-31-preview"
    response = requests.get(url, headers=headers)
    #
    # Check if the request was successful
    if response.status_code == 200:
        analysis_results = response.text
        # Process the analysis results as needed
        with open('rest-response.json', 'w', encoding="utf-8") as f:
            f.write(analysis_results)
        return response.json()["analyzeResult"]
    else:
        print(f"Error: {response.status_code} - {response.text}")

def parse_result(result):
    #
    paragraphs = {}
    for idx, paragraph in enumerate(result.get("paragraphs", [])):
        paragraphs[f"/paragraphs/{idx}"] = paragraph
    if not paragraphs:
        print("Error. Paragraphs Not Found.")
        return
    #
    pdfPage = PDFPage()
    #
    sectionIdx = {}
    for idx, section in enumerate(result.get("sections", [])):
        key = f"/sections/{idx}"
        #
        pdfSection = sectionIdx.get(key)
        if pdfSection is None:
            pdfSection = PDFPageSection(path=key)
            pdfPage.sections.append(pdfSection)
            sectionIdx[key] = pdfSection
        #
        for element in section["elements"]:
            print(f"{idx}, {element}")
            if element.startswith("/sections/"):
                sub = PDFPageSection(path=element)
                pdfSection.subSections.append(sub)
                sectionIdx[element] = sub
            elif element.startswith("/paragraphs/"):
                role = parse_paragraph(pdfSection, paragraphs[element])
                if role == 'footnote':
                    pdfSection = sectionIdx.get("footnote")
                    if pdfSection is None:
                        pdfSection = PDFPageSection(path='footnote')
                        pdfPage.sections.append(pdfSection)
                        sectionIdx["footnote"] = pdfSection
                    parse_notes(pdfSection, paragraphs[element])
                elif role == 'pageFooter':
                    pdfSection = sectionIdx.get("pageFooter")
                    if pdfSection is None:
                        pdfSection = PDFPageSection(path='pageFooter')
                        pdfPage.sections.append(pdfSection)
                        sectionIdx["pageFooter"] = pdfSection
                    parse_notes(pdfSection, paragraphs[element])
                elif role == 'pageHeader':
                    pdfSection = sectionIdx.get("pageHeader")
                    if pdfSection is None:
                        pdfSection = PDFPageSection(path='pageHeader')
                        pdfPage.sections.append(pdfSection)
                        sectionIdx["pageHeader"] = pdfSection
                    parse_notes(pdfSection, paragraphs[element])

    # dump pdfPage to a json file
    with open("rest-analysis-result.json", "w") as f:
        f.write(pdfPage.model_dump_json())

def main():
    # Get the file path from the command line arguments
    file_path = "./sample.pdf"
    # Call the analyze function to start the analysis process
    operationId = submit_pdf(file_path)
    if operationId:
        print("waiting for result...")
        time.sleep(10)
        result = get_result(operationId)
        #
        parse_result(result)

if __name__ == "__main__":
    #main()
    result = get_result("3c601054-2b4c-4b79-ab7a-bfffd7a79eeb")
    parse_result(result)