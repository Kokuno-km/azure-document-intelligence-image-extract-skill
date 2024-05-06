from PIL import Image
import fitz  # PyMuPDF
import mimetypes
import requests
import base64
from mimetypes import guess_type
from io import BytesIO
import re
from urllib.parse import urlparse, unquote
import os
# Function to encode a local image into data URL 
def local_image_to_data_url(image_path):
    # Guess the MIME type of the image based on the file extension
    mime_type, _ = guess_type(image_path)
    if mime_type is None:
        mime_type = 'application/octet-stream'  # Default MIME type if none is found

    # Read and encode the image file
    with open(image_path, "rb") as image_file:
        base64_encoded_data = base64.b64encode(image_file.read()).decode('utf-8')

    # Construct the data URL
    return f"data:{mime_type};base64,{base64_encoded_data}"

def crop_image_from_image(image_path, page_number, bounding_box):
    """
    Crops an image based on a bounding box.

    :param image_path: Path to the image file.
    :param page_number: The page number of the image to crop (for TIFF format).
    :param bounding_box: A tuple of (left, upper, right, lower) coordinates for the bounding box.
    :return: A cropped image.
    :rtype: PIL.Image.Image
    """
    with Image.open(image_path) as img:
        if img.format == "TIFF":
            # Open the TIFF image
            img.seek(page_number)
            img = img.copy()
            
        # The bounding box is expected to be in the format (left, upper, right, lower).
        cropped_image = img.crop(bounding_box)
        return cropped_image

def crop_image_from_pdf_page(pdf_path, page_number, bounding_box):
    """
    Crops a region from a given page in a PDF and returns it as an image.

    :param pdf_path: Path to the PDF file.
    :param page_number: The page number to crop from (0-indexed).
    :param bounding_box: A tuple of (x0, y0, x1, y1) coordinates for the bounding box.
    :return: A PIL Image of the cropped area.
    """
    doc = fitz.open(pdf_path)
    page = doc.load_page(page_number)
    
    # Cropping the page. The rect requires the coordinates in the format (x0, y0, x1, y1).
    # The coordinates are in points (1/72 inch).
    bbx = [x * 72 for x in bounding_box]
    rect = fitz.Rect(bbx)
    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72), clip=rect)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()

    return img

def crop_image_from_pdf_url(doc, page_number, bounding_box):
    page = doc.load_page(page_number)
    bbx = [x * 72 for x in bounding_box]
    rect = fitz.Rect(bbx)
    pix = page.get_pixmap(matrix=fitz.Matrix(300/72, 300/72), clip=rect)
    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    doc.close()
    return img

def crop_image_from_file(file_path, page_number, bounding_box):
    """
    Crop an image from a file.

    Args:
        file_path (str): The path to the file.
        page_number (int): The page number (for PDF and TIFF files, 0-indexed).
        bounding_box (tuple): The bounding box coordinates in the format (x0, y0, x1, y1).

    Returns:
        A PIL Image of the cropped area.
    """
    mime_type = mimetypes.guess_type(file_path)[0]
    if file_path.startswith("http://") or file_path.startswith("https://"):
        # URL から PDF ドキュメントを開く
        document = open_pdf_from_url(file_path)
        return crop_image_from_pdf_url(document, page_number, bounding_box)
    elif mime_type == "application/pdf":
        return crop_image_from_pdf_page(file_path, page_number, bounding_box)
    else:
        return crop_image_from_image(file_path, page_number, bounding_box)
    
def open_pdf_from_url(url):
    # PDF ファイルをダウンロード
    response = requests.get(url)
    response.raise_for_status()  # ネットワークエラー等があればここで例外を発生させる

    # メモリ上で PDF ファイルを開く
    pdf_file = BytesIO(response.content)
    document = fitz.open("pdf", pdf_file)

    return document

def polygon_to_bounding_box(polygon):
    """
    Translates a polygon to a bounding box.

    :param polygon: A list of (x, y) coordinates of the polygon.
    :return: A bounding box in the format (x0, y0, x1, y1).
    """

    x0 = polygon[0]
    y0 = polygon[1]
    x1 = polygon[4]
    y1 = polygon[5]
    
    return (x0, y0, x1, y1)

def safe_filename(filename):
    # 一般的に安全でない文字をアンダースコアに置換
    safe_name = re.sub(r'[^a-zA-Z0-9_.-]', '_', filename)
    # 連続するアンダースコアを一つに縮小
    safe_name = re.sub(r'__+', '_', safe_name)
    # 先頭と末尾のアンダースコアを削除
    safe_name = safe_name.strip('_')
    # 全て小文字に変換
    safe_name = safe_name.lower()
    
    return safe_name

def get_filename_from_url(url):
    # URLをパースしてパス部分を取得
    parsed_url = urlparse(url)
    # パスからファイル名を抽出
    filename = os.path.basename(parsed_url.path)
    # URLデコードを行う
    return unquote(filename)