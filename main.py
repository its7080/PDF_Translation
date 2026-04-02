import os
from datetime import datetime
from PyPDF2 import PdfReader, PdfWriter

def split_pdf(input_path, chunk_size=25):
    # Load PDF
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)

    print(f"Total pages: {total_pages}")

    # Create output folder with datetime
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    output_folder = f"split_output_{timestamp}"
    os.makedirs(output_folder, exist_ok=True)

    # Split logic
    part = 1
    for start in range(0, total_pages, chunk_size):
        writer = PdfWriter()
        end = min(start + chunk_size, total_pages)

        # Add pages to writer
        for i in range(start, end):
            writer.add_page(reader.pages[i])

        # File name like: part_1_1-40.pdf
        output_filename = f"part_{part}_{start+1}-{end}.pdf"
        output_path = os.path.join(output_folder, output_filename)

        # Save file
        with open(output_path, "wb") as f:
            writer.write(f)

        print(f"Saved: {output_filename}")
        part += 1

    print(f"\nAll files saved in folder: {output_folder}")


if __name__ == "__main__":
    pdf_path = input("Enter full path of PDF file: ").strip()

    if not os.path.isfile(pdf_path):
        print("Invalid file path!")
    else:
        split_pdf(pdf_path)