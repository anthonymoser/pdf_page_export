import streamlit as st
import base64
import sqlite3
import os
from zipfile import ZipFile
import PyPDF2
from PyPDF2 import PdfFileReader, PdfFileWriter

conn = sqlite3.connect('TEMP.db')
conn.row_factory = sqlite3.Row # trick!
cursor = conn.cursor()


def check_for_folder(folder_path, folder_name):
    if not os.path.isdir(f'{folder_path}/{folder_name}'):
        os.mkdir(f'{folder_path}/{folder_name}')


def initialize_db():
    global cursor
    sql = "SELECT name FROM sqlite_master WHERE type='table' AND name='exports';"
    cursor.execute(sql)
    exists = cursor.fetchone()
    if not exists:
        cursor.execute("CREATE TABLE exports(source_file TEXT NOT NULL, filename TEXT NOT NULL, page_list TEXT)")
        conn.commit()


def add_export(filename, page_list, exports):
    if filename in [e['filename'] for e in exports]:
        cursor.execute("UPDATE exports SET page_list = ? WHERE source_file = ? AND filename = ?", [page_list, source_file, filename])
    else:
        cursor.execute("INSERT INTO exports(source_file, filename, page_list) VALUES (?, ?, ?)", [source_file, filename, page_list])
    conn.commit()


def update_export_list(exports):
    global export_frame
    output = ""
    for e in exports:
        output += f"{e['filename']}: {e['page_list']}\n"
    export_frame.text(output)


def get_exports(source_file):
    cursor.execute('SELECT filename, page_list FROM exports WHERE source_file = ?', [source_file])
    exports = cursor.fetchall()
    return exports


def export_files(exports):
    source = PdfFileReader(open(source_file, "rb"))
    exported = []
    for ex in exports:
        try:
            exported_file = export_file(ex['filename'], ex['page_list'], source)
            exported.append(exported_file)
        except Exception as e:
            print("Failed to export ", ex)
            print(e)
            continue
    attachments = export_attachments(source)
    return exported, attachments


def search(data: dict, depth=0):
    global attachments
    for key, value in data.items():
        if key == "/FS":
            meta = value.getObject()
            print("    File found: ", meta['/F'])
            attachments[meta['/F']] = meta['/EF']['/F'].getData()
        elif key == "/Parent":
            # This prevents recursion errors
            pass
        else:
            check_object(value, depth + 1)



def check_object(obj, depth=0):
    global attachments
    if isinstance(obj, PyPDF2.generic.IndirectObject):
        obj = obj.getObject()
    if isinstance(obj, dict):
        search(obj, depth + 1)
    if isinstance(obj, list):
        for o in obj:
            check_object(o, depth + 1)


def export_attachments(source):
    global attachments
    attachments = {}
    file_list = []
    try:
        search(source.trailer["/Root"])
        if attachments:
            check_for_folder(f'./{source_file[:-4]}', 'attachments')
        for attachment_name, attachment_data in attachments.items():
            with open(f'./{source_file[:-4]}/attachments/{attachment_name}', 'wb') as outfile:
                outfile.write(attachment_data)
            file_list.append(f'./{source_file[:-4]}/attachments/{attachment_name}')
    except Exception as e:
        print(e)
    return file_list


def export_file(filename, page_list, source):
    pages = page_list.replace(' ', '').split(',')
    page_numbers = []
    # Parse page_list string into a list of integers
    for p in pages:
        if '-' in p:
            p_range = p.split('-')
            p_start = int(p_range[0])
            p_end = int(p_range[1])
            page_numbers.extend([x for x in range(p_start, p_end + 1)])
        else:
            page_numbers.append(int(p))
    source_length = source.getNumPages()
    new_pdf = PdfFileWriter()
    for pn in page_numbers:
        if 0 < pn <= source_length:
            new_pdf.addPage(source.getPage(pn - 1))
    export_path = f"./{source_file[:-4]}/{filename}.pdf"
    with open(export_path, 'wb') as export:
        new_pdf.write(export)
    return export_path


def save_uploadedfile(uploadedfile):
    with open(uploadedfile.name, "wb") as f:
        f.write(uploadedfile.getbuffer())


def get_zip_link(download_filename):
    with open(download_filename, "rb") as f:
        bytes = f.read()
        b64 = base64.b64encode(bytes).decode()
    href = f'<a href="data:file/zip;base64,{b64}" download="{download_filename}">{download_filename}</a>'
    return href

st.set_page_config(
    layout="wide",  # Can be "centered" or "wide". In the future also "dashboard", etc.
    initial_sidebar_state="expanded",  # Can be "auto", "expanded", "collapsed"
    page_title='PDF Splitter',  # String or None. Strings get appended with "• Streamlit".
    page_icon=None,  # String, anything supported by st.image, or None.
)
initialize_db()
# st.text('Export PDF pages as new files')
with open("readme.md", "r") as f:
    fileString = f.read()
main_content = st.markdown(fileString)
datafile = st.sidebar.file_uploader("Upload PDF",type=['pdf'])
show_pdf = st.sidebar.checkbox("Show PDF")
filename = st.sidebar.text_input("Export name: ")
page_list = st.sidebar.text_input("Pages: ")
add_new_export = st.sidebar.button('Add export')
export_pdfs = st.sidebar.button('Export PDFs')
export_frame = st.sidebar.text('')

if datafile is not None:
    file_details = {"FileName":datafile.name,"FileType":datafile.type}
    save_uploadedfile(datafile)
    source_file = datafile.name
    with open(source_file, "rb") as f:
        base64_pdf = base64.b64encode(f.read()).decode('utf-8')
    if show_pdf:
        pdf_display = F'<embed src="data:application/pdf;base64,{base64_pdf}" width="800" height="800" type="application/pdf">'
        st.markdown(pdf_display, unsafe_allow_html=True)

    exports = get_exports(source_file)
    update_export_list(exports)

if add_new_export:
    add_export(filename, page_list, exports)
    exports = get_exports(source_file)
    update_export_list(exports)

if export_pdfs:
    exports = get_exports(source_file)
    check_for_folder('.', source_file[:-4])
    # check_for_folder(f'./{source_file[:-4]}', 'attachments')
    exported_files, attachments = export_files(exports)
    print(exported_files)

    with ZipFile(f'{source_file[:-4]}.zip', 'w') as outzip:
        for ef in exported_files:
            outzip.write(ef)
        for a in attachments:
            outzip.write(a)

    st.sidebar.success('EXPORT COMPLETE')
    st.sidebar.markdown(get_zip_link(f'{source_file[:-4]}.zip'), unsafe_allow_html=True)
