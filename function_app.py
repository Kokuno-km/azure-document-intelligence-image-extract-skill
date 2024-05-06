import azure.functions as func
import logging
import json
import os
import io
import datetime, time
from json import JSONEncoder
from azure.core.credentials import AzureKeyCredential
from azure.ai.documentintelligence import DocumentIntelligenceClient
from azure.ai.documentintelligence.models import AnalyzeDocumentRequest, AnalyzeResult
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from extractimages import crop_image_from_file, get_filename_from_url, polygon_to_bounding_box, safe_filename

app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)

class DateTimeEncoder(JSONEncoder):
    #Override the default method    
    def default(self, obj):
        if isinstance(obj, (datetime.date, datetime.datetime)):
            return obj.isoformat()

def get_tables(result):
    tables = []
    for table_idx, table in enumerate(result.tables):
        cells = []
        for cell in table.cells: 
            cells.append( {
                "row_index": cell.row_index,
                "column_index": cell.column_index,
                "content": cell.content,
            })
        tab = {
                "row_count": table.row_count,
                "column_count": table.column_count,
                "cells": cells
        }
        tables.append(tab)
        return tables

def get_pages(result):
    pages = []
    for page in result.pages:
        lines = []
        for line_idx, line in enumerate(page.lines):
            lines.append(line.content)
        pages.append(lines)
    return pages

def get_content(result):
    content = ""
    if result.content:
        content = result.content
    return content

def get_paragraphs(result):
    paragraphs = []
    for idx, paragraph in enumerate(result.paragraphs):
        item = {
            "id": "paragraphs/" + str(idx),
            "content": paragraph.content if paragraph.content else "",
            "role": paragraph.role if paragraph.role else "",
        }
        paragraphs.append(item)
    return paragraphs

def get_sections(result):
    sections = []
    for section in result.sections:
        sections.append(section.elements)
    return sections

def save_to_blob_images(img_bytes, parent_dir, image_filename, metadata):
    # 環境変数から Azure Storage 接続文字列を取得
    connect_str = os.environ['AZURE_STORAGE_CONNECTION_STRING']
    container_name = os.environ['AZURE_STORAGE_CONTAINER_NAME']

    # Blob Service クライアントを初期化
    blob_service_client = BlobServiceClient.from_connection_string(connect_str)
    # Blob のパスを構築
    blob_name = f"{parent_dir}/{image_filename}"

    blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)

    # Blob Storage にアップロード
    blob_client.upload_blob(img_bytes, blob_type="BlockBlob", overwrite=True)
    # メタデータを設定
    blob_client.set_blob_metadata(metadata)

def extract_images(result, pdf_path):
    if result.figures:
        figs = []
        for idx, figures in enumerate(result.figures):
            print(f"--------Analysis of Figures #{idx + 1}--------")
            caption = ""
            captionBR = []

            if figures.caption:
                caption = figures.caption.get("content")
                if caption:
                    print(f"Caption: {caption}")

                caption_boundingRegions = figures.caption.get("boundingRegions")
                if caption_boundingRegions:
                    for item in caption_boundingRegions:
                        captionBR = item.get('polygon')

            boundingRegions = figures.get("boundingRegions")
            if boundingRegions:
                for item in boundingRegions:
                    if captionBR != item.get('polygon'): #caption の polygon を除外したい
                        image = crop_image_from_file(pdf_path, item.get('pageNumber') - 1, polygon_to_bounding_box(item.get('polygon')))
                        img_bytes = io.BytesIO()
                        image.save(img_bytes, format='PNG') # 画像をバイト配列としてメモリ上に保存
                        img_bytes.seek(0)

                        metadata = {
                            "parent": pdf_path,
                            "pageNumber": str(item.get('pageNumber')),
                            "caption": caption,
                            "image": safe_filename(f"figure_{idx + 1}_{caption}.png"),
                            "polygon": str([str(f) for f in item.get('polygon')]),
                            "elements": str([str(e) for e in figures.elements]) if figures.elements else ""
                        }
                        save_to_blob_images(img_bytes, get_filename_from_url(pdf_path).replace('.', '_'), safe_filename(f"figure_{idx + 1}_{caption}.png"), metadata)

                        returndata = {
                            "pageNumber": item.get('pageNumber'),
                            "caption": caption,
                            "image": safe_filename(f"figure_{idx + 1}_{caption}.png"),
                            "polygon": item.get('polygon'),
                            "elements": figures.elements if figures.elements else ""
                        }

                        figs.append(returndata)
    return figs

def compose_response(json_data):
    values = json.loads(json_data)['values']
    
    # Prepare the Output before the loop
    results = {}
    results["values"] = []
    endpoint = os.environ["DOCUMENT_INTELLIGENCE_ENDPOINT"]
    key = os.environ["DOCUMENT_INTELLIGENCE_KEY"]
    
    for value in values:
        output_record = analyze_document(endpoint=endpoint, key=key, recordId=value["recordId"], data=value["data"])
        results["values"].append(output_record)

    return json.dumps(results, ensure_ascii=False, cls=DateTimeEncoder)


def analyze_document(endpoint, key, recordId, data):
    try:
        formUrl = data["formUrl"] + data["formSasToken"]
        model = data["model"]
        logging.info("formUrl: " + data["formUrl"])
        logging.info("Model: " + model)

        document_intelligence_client = DocumentIntelligenceClient(endpoint=endpoint, credential=AzureKeyCredential(key))
        poller = document_intelligence_client.begin_analyze_document(
            model, AnalyzeDocumentRequest(url_source=formUrl),output_content_format="markdown"
        )
        result = poller.result()
        logging.info("Result from Document Intelligence")
        output_record = {}
        output_record_data = {}
        if  model == "prebuilt-layout":
            output_record_data = { 
                #"tables": get_tables(result), #必要であれば有効化
                #"pages": get_pages(result), #必要であれば有効化
                "paragraphs": get_paragraphs(result),
                "sections": get_sections(result),
                "content": get_content(result),
                "figures": extract_images(result, formUrl)
        }

        output_record = {
            "recordId": recordId,
            "data": output_record_data
        }

    except Exception as error:
        output_record = {
            "recordId": recordId,
            "errors": [ { "message": "Error: " + str(error) }   ] 
        }

    logging.info("Output record: " + json.dumps(output_record, ensure_ascii=False, cls=DateTimeEncoder))
    return output_record


@app.route(route="analyze")
def analyze(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Invoked Document Intelligence Image Extract Skill.')
    try:
        body = json.dumps(req.get_json())

        if body:
            logging.info(body)
            result = compose_response(body)
            logging.info("Result to return to custom skill")
            return func.HttpResponse(result, mimetype="application/json")
        else:
            return func.HttpResponse(
                "Invalid body",
                status_code=400
            )
    except ValueError:
        return func.HttpResponse(
             "Invalid body",
             status_code=400
        )