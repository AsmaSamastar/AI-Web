from fpdf.ttfonts import TTFontFile
import warnings
from pypdf import PdfReader
from flask_cors import CORS
from fpdf import FPDF
import os
import openai
from flask import jsonify  # 导入jsonify函数
from flask import render_template
from flask import Flask, request, send_file
from werkzeug.utils import secure_filename
from textwrap import wrap

import tiktoken
tokenizer = tiktoken.get_encoding("cl100k_base")


# 忽略FPDF库的特定警告
warnings.filterwarnings("ignore", category=UserWarning,
                        module="fpdf.ttfonts", lineno=670)


app = Flask(__name__, static_folder='static')
app.config['UPLOAD_FOLDER'] = 'uploads/'  # 设置上传文件的存储路径

cors = CORS(app, resources={r"/*": {"origins": "*"}})  # 允许所有域名访问

# 替换为你的OpenAI API key
openai.api_key = os.getenv('OPENAI_API_KEY')

max_length = 13000


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
    # 定义提示，让模型知道它需要删除重复的内容

    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages
    )

    return response.choices[0].message['content']


def summarize_with_gpt_longText(text, prompt):
    paragraphs = split_text_into_paragraphs(text)

    # 初始化一个空的结果列表来保存GPT-3的所有答案
    results = []

    # 将段落作为助理消息添加到messages列表中
    for paragraph in paragraphs:

        # 创建一个messages列表并添加一个系统消息
        messages = [
            {"role": "system", "content": "You are an assistant who extract scientific data and summarise them for researchers."}]
        # 将段落和问题添加到消息中
        messages.append({"role": "user", "content": paragraph})
        messages.append({"role": "assistant", "content": prompt})

        # 创建聊天完成请求
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=messages
        )

        # 保存GPT-3的答案
        answer = response.choices[0].message['content']
        results.append(answer)

        messages = []

    # 最终，results包含了从每一段中提取的关键信息
    final_output = ' '.join(results)

    # 使用 GPT 模型删除整个文本的重复内容
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
    data = request.get_json()
    text = data['text']
    prompt = data['prompt']

    length_of_tokenized_text = len(tokenizer.encode(text))

    if len(tokenizer.encode(text)) <= max_length:
        summary = summarize_with_gpt(text, prompt)
    else:
        summary = summarize_with_gpt_longText(text, prompt)

    return jsonify({'summary': summary})


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

    # 返回一个包含多个文本的JSON对象
    return jsonify({'texts': texts})


def extract_text_from_pdf(file_path):
    text = ""
    reader = PdfReader(file_path)
    for page_num in range(len(reader.pages)):
        text += reader.pages[page_num].extract_text()
    return text


@app.route('/downloadSummaries', methods=['POST'])
def download_summaries():
    # 从请求中获取摘要内容
    summaries_data_list = request.json['summaries']  # 获取整个摘要列表

    # 创建PDF文档
    pdf = FPDF()
    pdf.add_page()

    # 加载DejaVu字体
    pdf.add_font('DejaVu', '', 'DejaVuSansCondensed.ttf', uni=True)
    pdf.set_font('DejaVu', size=11)

    # 单元格宽度
    col_widths = [60, 130]

    # 遍历所有摘要，并将它们添加到PDF文档中
    for summaries_data in summaries_data_list:
        for summary_group in summaries_data:
            title = summary_group['title']
            content = summary_group['content']

            # 计算title的行数
            title_lines = title.split('\n')
            num_lines = len(title_lines)

            # 添加title和content
            for i, line in enumerate(title_lines):
                pdf.cell(col_widths[0], 10, txt=line, border=1)
                if i == 0:
                    pdf.multi_cell(col_widths[1], 10 * num_lines, txt=content, border=1)
                else:
                    pdf.cell(col_widths[1], 10, txt='', border=1)
                pdf.ln()

    # 保存PDF到临时文件
    pdf_path = "temp_summaries.pdf"
    pdf.output(pdf_path)

    # 打开PDF文件
    f = open(pdf_path, 'rb')

    # 发送PDF文件作为响应
    return send_file(f, as_attachment=True, download_name='summaries.pdf')



if __name__ == '__main__':
    if not os.path.exists(app.config['UPLOAD_FOLDER']):  # 如果存储路径不存在，创建一个新的
        os.makedirs(app.config['UPLOAD_FOLDER'])

    app.run(debug=True)
