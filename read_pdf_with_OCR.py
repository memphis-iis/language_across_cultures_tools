# Description: Extract text from PDF files using PyMuPDF and Tesseract OCR

import os
import fitz  # PyMuPDF
import re
import unicodedata
from PIL import Image
import pytesseract

def pdf_to_text(pdf_file_path):
    text = ""
    try:
        pdf_document = fitz.open(pdf_file_path)
        for page_num in range(pdf_document.page_count):
            page = pdf_document.load_page(page_num)
            text += page.get_text("text")
    except Exception as e:
        print(f"Error processing PDF {pdf_file_path}: {str(e)}")
    return text

def save_text_as_txt(pdf_file_path, text):
    txt_filename = os.path.splitext(pdf_file_path)[0] + ".txt"
    with open(txt_filename, "w", encoding="utf-8") as txt_file:
        txt_file.write(text)

def filter_paragraphs(text, min_words=5):
    # Split text into paragraphs using empty lines as separators
    paragraphs = re.split(r'\n\s*\n', text)

    # Filter paragraphs with at least min_words words and not all uppercase
    filtered_paragraphs = [p for p in paragraphs if (len(re.findall(r'\S+', p)) >= min_words) and not p.isupper()]

    # Remove non-ASCII characters and hyphens
    filtered_paragraphs = [re.sub(r'[^\x00-\x7F-]', '', p) for p in filtered_paragraphs]

    return "\n".join(filtered_paragraphs)

def main(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith(".pdf"):
                pdf_path = os.path.join(root, file)
                text = pdf_to_text(pdf_path)
                if text.strip():
                    filtered_text = filter_paragraphs(text, min_words=5)
                    if filtered_text.strip():
                        print(f"Text extracted from {pdf_path}:")
                        print(filtered_text)
                        save_text_as_txt(pdf_path, filtered_text)
                        print(f"Text saved as {os.path.splitext(pdf_path)[0]}.txt")
                        print()
                    else:
                        print(f"No suitable paragraphs found in {pdf_path}")

if __name__ == "__main__":
    folder_path = "./pdf_statements"
    main(folder_path)
