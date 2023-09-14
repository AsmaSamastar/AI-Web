from fpdf.ttfonts import TTFontFile
import warnings
from pypdf import PdfReader
from flask_cors import CORS
from fpdf import FPDF
import os
import base64
import openai
from flask import jsonify
from flask import render_template
from flask import Flask, request, send_file
from werkzeug.utils import secure_filename
from textwrap import wrap

from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, Content, Attachment, FileContent, FileName, FileType, Disposition

import tiktoken
tokenizer = tiktoken.get_encoding("cl100k_base")


warnings.filterwarnings("ignore", category=UserWarning,
                        module="fpdf.ttfonts", lineno=670)


app = Flask(__name__, static_folder='static')
app.config['UPLOAD_FOLDER'] = 'uploads/'

cors = CORS(app, resources={r"/*": {"origins": "*"}})

openai.api_key = os.getenv('OPENAI_API_KEY')

max_length = 13000


@app.route('/', methods=['GET'])
def home():
    return render_template("index.html")


@app.route('/upload', methods=['POST'])
def upload_file():
    if 'pdfUpload' not in request.files:
        return 'No file part', 400
    files = request.files.getlist('pdfUpload')

    texts = []
    for file in files:
        if file:
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(file_path)
            text = extract_text_from_pdf(file_path)
            texts.append(text)

    return jsonify({'texts': texts})


def extract_text_from_pdf(file_path):
    text = ""
    reader = PdfReader(file_path)
    for page_num in range(len(reader.pages)):
        text += reader.pages[page_num].extract_text()
    return text


def split_text_into_paragraphs(text):
    paragraphs = text.split('\n')
    current_length = 0
    current_paragraphs = []
    results = []

    for paragraph in paragraphs:
        if current_length + len(tokenizer.encode(paragraph)) > max_length:
            results.append('\n\n'.join(current_paragraphs))
            current_paragraphs = []
            current_length = 0
        current_paragraphs.append(paragraph)
        current_length += len(tokenizer.encode(paragraph))

    if current_paragraphs:
        results.append('\n\n'.join(current_paragraphs))

    return results


def remove_duplicates_with_gpt(text):

    messages = [{"role": "system", "content": "Please remove any repetitive information from the text. Please note that only the repetitive information should be removed and nothing else should be changed."}]
    messages.append({"role": "user", "content": text})

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )

    return response.choices[0].message['content']


def summarize_with_gpt_longText(text, prompt):
    paragraphs = split_text_into_paragraphs(text)

    results = []

    for paragraph in paragraphs:

        messages = [
            {"role": "system", "content": "You are an assistant who extract scientific data and summarise them for researchers."}]

        messages.append({"role": "user", "content": paragraph})
        messages.append({"role": "assistant", "content": prompt})

        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=messages
        )

        answer = response.choices[0].message['content']
        results.append(answer)

        messages = []

    final_output = ' '.join(results)

    final_output = remove_duplicates_with_gpt(final_output)

    return final_output


def summarize_with_gpt(text, prompt):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",
        messages=[
            {"role": "system", "content": "You are an assistant who extract scientific data and summarise them for researchers."},
            {"role": "assistant", "content": text},
            {"role": "user", "content": prompt},
        ]
    )

    return response.choices[0].message['content']


@app.route('/generateSummary', methods=['POST'])
def generate_summary():
    try:
        data = request.get_json()
        text = data['text']
        prompt = data['prompt']

        length_of_tokenized_text = len(tokenizer.encode(text))

        if len(tokenizer.encode(text)) <= max_length:
            summary = summarize_with_gpt(text, prompt)
        else:
            summary = summarize_with_gpt_longText(text, prompt)

        return jsonify({'summary': summary})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def send_email_with_attachment(to_email, subject, content, pdf_path):
    from_email = 'admin@sumarizer.com'

    message = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=content)

    with open('static/logo.png', 'rb') as f:
        data = f.read()
    encoded = base64.b64encode(data).decode()
    attachedLogo = Attachment(
        FileContent(encoded),
        FileName('logo.png'),
        FileType('image/png'),
        Disposition('inline'),
        content_id='Logo')
    message.add_attachment(attachedLogo)

    if pdf_path is not None:
        with open(pdf_path, 'rb') as f:
            data = f.read()
            f.close()
        encoded = base64.b64encode(data).decode()
        attachedFile = Attachment(
            FileContent(encoded),
            FileName('Sumarizer-Summary.pdf'),
            FileType('application/pdf'),
            Disposition('attachment'))
        message.attachment = attachedFile

    try:
        sg = SendGridAPIClient(os.getenv('SENDGRID_API_KEY'))
        response = sg.send(message)
        return response.status_code, response.body, response.headers
    except Exception as e:
        print(str(e))
        return None, None, None


def create_pdf(pdf_path, summaries_data_list):

    class PDF(FPDF):
        def header(self):

            self.set_font('DejaVu', 'B', 15)

            self.cell(80)

            self.image('static/logo.png', 10, 8, 33)
            self.ln(20)

        def footer(self):

            self.set_y(-15)

            self.set_font('DejaVu', 'I', 12)

            self.cell(0, 10, 'Page ' + str(self.page_no()) +
                      ' of {nb}', 0, 0, 'C')

            self.cell(0, 10, 'sumarizer.com', 0, 0, 'R')

    pdf = PDF()
    pdf.alias_nb_pages()
    pdf.add_font('DejaVu', '', 'DejaVuSansCondensed.ttf', uni=True)
    pdf.add_font('DejaVu', 'B', 'DejaVuSansCondensed-Bold.ttf', uni=True)
    pdf.add_font('DejaVu', 'I', 'DejaVuSerifCondensed-Italic.ttf', uni=True)
    pdf.add_page()

    content_font_size = 11
    title_font_size = content_font_size + 3 

    cell_width = 190

    for summaries_data in summaries_data_list:
        for summary_group in summaries_data:
            title = summary_group['title']
            content = summary_group['content']

            pdf.set_font('DejaVu', 'B', title_font_size)
            pdf.cell(cell_width, 10, txt=title, border=1)
            pdf.ln() 

            pdf.set_font('DejaVu', '', content_font_size)  
            pdf.multi_cell(cell_width, 10, txt=content, border=1)
            
        pdf.ln(10)

    pdf.output(pdf_path)


@app.route('/sendEmail', methods=['POST'])
def send_email():

    data = request.json
    name = data['name']
    email = data['email']
    summaries_data_list = data['summaries']

    pdf_path = "temp_summaries.pdf"
    create_pdf(pdf_path, summaries_data_list)

    subject = "Your PDF Summary"

    content = f"""
    <img src="cid:Logo" alt="Sumarizer Logo">
    <p>Hello {name},</p>
    <p>Here is your PDF summary.</p>
    <a href="https://sumarizer.com">https://sumarizer.com</a>
    """

    status, _, _ = send_email_with_attachment(
        email, subject, content, pdf_path)

    if status == 202:
        os.remove(pdf_path)
        return jsonify({'status': 'ok'})

    else:
        print(f"Error sending email. Status code: {status}")
        return jsonify({'status': 'error', 'message': 'Failed to send email'}), 500


@app.route('/sendFeedback', methods=['POST'])
def send_feedback():
    try:
        data = request.json
        rating = data['rating']
        feedback = data['feedback']

        subject = "New Feedback Received"

        content = """
        <table border='1'>
            <tr>
                <th>Rating</th>
                <td>{}</td>
            </tr>
            <tr>
                <th>Feedback</th>
                <td>{}</td>
            </tr>
        </table>
        """.format(rating, feedback)

        to_email = 'sumarizer-feedback@samastar.co.uk'

        _, _, _ = send_email_with_attachment(to_email, subject, content, None)

        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})



if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])

    app.run(debug=True)
