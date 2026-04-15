import pymupdf
import os
import random
import regex
from collections import Counter
print(os.getcwd())

legal_data_path = os.path.join(os.getcwd(), "data", "legal-data")

def count_session_header(legal_data_path):
    for _ in range(5):
        sample = random.sample(os.listdir(legal_data_path), 1000)
        contain_text, contain_image, contain_both, contain_nothing = 0, 0, 0, 0
        for filename in sample:
            filepath = os.path.join(legal_data_path, filename)
            for page in pymupdf.open(filepath):
                text_is_avai = len(page.get_text().strip()) > 50
                image_is_avai = len(page.get_images()) > 0
                if text_is_avai and image_is_avai:
                    contain_both += 1                                                                       
                elif text_is_avai:
                    contain_text += 1                                                                       
                elif image_is_avai:
                    contain_image += 1
                else:
                    contain_nothing += 1

        print(f"step {_}: contain text: {contain_text}, contain images: {contain_image}")
        print(f"step {_}: contain both: {contain_both}, contain nothing: {contain_nothing}")

def count_session_header(legal_data_path):
    for _ in range(5):
        sample = random.sample(os.listdir(legal_data_path), 1000)
        header_section_counter = Counter()

        for filename in sample:
            filepath = os.path.join(legal_data_path, filename)
            for page in pymupdf.open(filepath):
                results = regex.findall(r'[\p{Lu}]{2,}[\p{Lu}\s]*', page.get_text())             
                for i in results:
                    if i not in header_section_counter:
                        header_section_counter[i] = 0
                    header_section_counter[i] += 1
        for key, value in header_section_counter.most_common(30):
            print(f"{key}: {value}")

count_session_header(legal_data_path=legal_data_path)
