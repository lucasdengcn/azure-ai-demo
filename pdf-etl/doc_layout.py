# import libraries
import os
import time
import base64
import json
from pydantic import BaseModel
from typing import List, Optional

from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeResult
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest

#
from dotenv import load_dotenv
load_dotenv()

# helper functions

def get_words(page, line):
    result = []
    for word in page.words:
        if _in_span(word, line.spans):
            result.append(word)
    return result


def _in_span(word, spans):
    for span in spans:
        if word.span.offset >= span.offset and (
            word.span.offset + word.span.length
        ) <= (span.offset + span.length):
            return True
    return False

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


def parse_paragraph(section, paragraph) -> None:
    print(f"paragraph role: {paragraph.role}")
    if paragraph.role == "sectionHeading":
        section.heading = paragraph.content
    else:
        section.paragraphs.append(paragraph.content)

def analyze_layout():
    # sample document
    with open("./sample.pdf", "rb") as f:
        base64_encoded_pdf = base64.b64encode(f.read()).decode("utf-8")

    #
    endpoint = os.getenv("ENDPOINT")
    key = os.getenv("KEY")

    print(f"{endpoint}, {key}")
    #
    start_time = time.time()
    document_intelligence_client = DocumentIntelligenceClient(
        endpoint=endpoint, credential=AzureKeyCredential(key)
    )

    # prebuilt-document
    poller = document_intelligence_client.begin_analyze_document(
        "prebuilt-layout", 
        AnalyzeDocumentRequest(bytes_source=base64_encoded_pdf),
        output_content_format="markdown",
        pages="1"
    )

    result: AnalyzeResult = poller.result()
    print(result.__class__.__name__)
    duration = time.time() - start_time
    print(f"api call duration: {duration}s")
    #
    if result.styles and any([style.is_handwritten for style in result.styles]):
        print("Document contains handwritten content")
    else:
        print("Document does not contain handwritten content")
    #
    with open("api-response.json", "w") as f:
        f.write(json.dumps(result.as_dict()))
    # index paragraphs
    paragraphs = {}
    for idx, paragraph in enumerate(result.paragraphs):
        paragraphs[f"/paragraphs/{idx}"] = paragraph
    #
    pdfPage = PDFPage()
    #
    sectionIdx = {}
    for idx, section in enumerate(result.sections):
        key = f"/sections/{idx}"
        #
        pdfSection = sectionIdx.get(key)
        if pdfSection is None:
            pdfSection = PDFPageSection(path=key)
            pdfPage.sections.append(pdfSection)
            sectionIdx[key] = pdfSection
        #
        for element in section.elements:
            print(f"{idx}, {element}")
            if element.startswith("/sections/"):
                sub = PDFPageSection(path=element)
                pdfSection.subSections.append(sub)
                sectionIdx[element] = sub
            elif element.startswith("/paragraphs/"):
                parse_paragraph(pdfSection, paragraphs[element])

    # dump pdfPage to a json file
    with open("layout-analysis.json", "w") as f:
        f.write(pdfPage.model_dump_json())

    #
    for page in result.pages:
        print(f"----Analyzing layout from page #{page.page_number}----")
        print(
            f"Page has width: {page.width} and height: {page.height}, measured with unit: {page.unit}"
        )

        if page.lines:
            for line_idx, line in enumerate(page.lines):
                words = get_words(page, line)
                print(
                    f"...Line # {line_idx} has word count {len(words)} and text '{line.content}' "
                    f"within bounding polygon '{line.polygon}'"
                )

                for word in words:
                    print(
                        f"......Word '{word.content}' has a confidence of {word.confidence}"
                    )

        if page.selection_marks:
            for selection_mark in page.selection_marks:
                print(
                    f"Selection mark is '{selection_mark.state}' within bounding polygon "
                    f"'{selection_mark.polygon}' and has a confidence of {selection_mark.confidence}"
                )

    if result.tables:
        for table_idx, table in enumerate(result.tables):
            print(
                f"Table # {table_idx} has {table.row_count} rows and "
                f"{table.column_count} columns"
            )
            if table.bounding_regions:
                for region in table.bounding_regions:
                    print(
                        f"Table # {table_idx} location on page: {region.page_number} is {region.polygon}"
                    )
            for cell in table.cells:
                print(
                    f"...Cell[{cell.row_index}][{cell.column_index}] has text '{cell.content}'"
                )
                if cell.bounding_regions:
                    for region in cell.bounding_regions:
                        print(
                            f"...content on page {region.page_number} is within bounding polygon '{region.polygon}'"
                        )

    print("----------------------------------------")


if __name__ == "__main__":
    analyze_layout()