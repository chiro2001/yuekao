from flask import *
from random import randint
import os
import time
import io
import hashlib
from datetime import datetime
import pytz
from upload import *
from PIL import Image, ImageDraw, ImageFont
from database import DataBase
import copy
import textwrap
import xlrd
import xlwt
import csv
import psycopg2
import sqlite3


app = Flask(__name__, static_folder='tmp')
app.secret_key = 'LianGunJianPanDaChuLaiDeZiNiXInBuXin'
db = DataBase()
with open('loss.txt', 'r', encoding='utf8') as f:
    captcha_data = f.read().split('\n\n')
print(len(captcha_data))


def local2utc(local_st):
    # 本地时间转UTC时间（-8:00）
    time_struct = time.mktime(local_st.timetuple())
    utc_st = datetime.utcfromtimestamp(time_struct)
    return utc_st


def xlsx_to_csv(xlsx_data: bytes):
    workbook = xlrd.open_workbook(file_contents=xlsx_data)
    table = workbook.sheet_by_index(0)
    csv_data = io.StringIO()
    write = csv.writer(csv_data)
    for row_num in range(table.nrows):
        row_value = table.row_values(row_num)
        write.writerow(row_value)
    csv_data.seek(0)
    return csv_data.read()


def csv_to_xlsx(csv_data: str):
    f = io.StringIO(csv_data)
    read = csv.reader(f)
    workbook = xlwt.Workbook()
    sheet = workbook.add_sheet('data')  # 创建一个sheet表格
    l = 0
    for line in read:
        # print(line)
        r = 0
        for i in line:
            # print(i)
            sheet.write(l, r, i)  # 一个一个将单元格数据写入
            r = r + 1
        l = l + 1
    xlsx_io = io.BytesIO()
    workbook.save(filename_or_stream=xlsx_io)  # 保存Excel
    xlsx_io.seek(0)
    return xlsx_io.read()


def captcha_get(string: str):
    empty = Image.new("RGB", (12, 12))
    font_num = ImageFont.truetype("segoeprb.ttf", 120)
    empty_draw = ImageDraw.Draw(empty)
    text_size = empty_draw.textsize(string, font=font_num)
    # print(text_size)
    im = Image.new("RGB", text_size, color='white')
    draw = ImageDraw.Draw(im)
    draw.ink = 0
    draw.text((0, 0 - 32), string, font=font_num)

    # 加入椒盐噪声
    for i in range(500):
        draw.point((randint(0, im.size[0] - 1), randint(0, im.size[1] - 1)), fill='white')
        draw.point((randint(0, im.size[0] - 1), randint(0, im.size[1] - 1)), fill='black')

    # 加上斜线
    for i in range(30):
        rand = (randint(0, im.size[0] - 1), randint(0, im.size[1] - 1))
        rand2 = (randint(0, im.size[0] - 1), randint(0, im.size[1] - 1))
        colors = ['white', 'black']
        # print(rand)
        draw.line((rand[0] * 2 - rand[0] // 2, rand[1] * 2 - rand[1] // 2,
                   rand2[0] * 2 - rand2[0] // 2, rand2[1] * 2 - rand2[1] // 2),
                  fill=colors[randint(0, 1)], width=randint(1, 3))

    # 画上背景
    rand_index = randint(0, len(captcha_data)-1)
    loss = captcha_data[rand_index]
    height = 32
    width = im.size[0] // height
    length = height * width // 32 * 32
    while length > len(loss):
        rand_index += 1
        if rand_index >= len(captcha_data) - 1:
            rand_index = 0
        loss += '\n' + captcha_data[rand_index]
    para = textwrap.wrap(loss, width=width)
    font_char = ImageFont.truetype('FZLTCXHJW.TTF', height)
    for line in para:
        draw.text((0, para.index(line) * height), line, font=font_char)

    return im


def generate_pass_port(limit=100):
    a = randint(0, limit)
    b = randint(0, limit)
    fun = [
        lambda x, y: x + y,
        lambda x, y: x - y,
    ]
    chars = '+-'
    p = randint(0, 1)
    s = '%d %s %d' % (a, chars[p], b)
    res_ = str(fun[p](a, b))
    return s, res_


def make_alert(message: str):
    return "<script>alert('%s');</script>" % message


# g_debug = True
g_debug = False
cdn = 'https://cdn-1254016670.cos.ap-chengdu.myqcloud.com/yuekao'
captcha_secret = 'Lian Gun Jian Pan Liang Ci Ni Xin Bu Xin'


@app.route('/', methods=['GET', 'POST'])
def index():
    if request.method == 'GET':
        args0 = dict(request.args)
        args = {}
        for arg in args0:
            val = args0[arg]
            if type(val) is list:
                args[arg] = val[0]
            else:
                args[arg] = val
        # 在主页删除状态
        # if 'login' in session:
        #     session['login'] = None

        s, res_ = generate_pass_port()
        md5 = hashlib.md5()
        md5.update(("%s[%s]" % (res_, captcha_secret)).encode())
        p = md5.hexdigest()
        # print('p=', p)
        captcha_get(s).save('tmp/captcha/%s.jpg' % p)
        return render_template('mo.html', passport='/tmp/captcha/%s.jpg' % p, s=p,
                               cdn=cdn, key_id=secret_id, key_key=secret_key, region=region, bucket=bucket)
    if request.method == 'POST':
        form = request.form
        if not g_debug:
            s = form['s']
            passport = form['passport']
            md5 = hashlib.md5()
            # md5.update(passport.encode())
            md5.update(("%s[%s]" % (passport, captcha_secret)).encode())
            p = md5.hexdigest()
            # print('in: passport=', passport, ' s=', s, ' p=', p)
            if os.path.exists('tmp/captcha/%s.jpg' % s):
                # 验证码失效
                os.remove('tmp/captcha/%s.jpg' % s)
            if p != s:
                return make_alert('验证码错误或者已经失效，请刷新页面重试。')
        if 'file' not in request.files:
            return make_alert('没有选择文件。')
        file = request.files['file']
        if file.filename == '':
            return make_alert('没有选择文件。')
        filename = str(file.filename)
        file_type = filename.split('.')[-1]
        filedata = io.BytesIO()
        file.save(filedata)
        filedata.seek(0)
        # print(filedata)
        # file.save(os.path.abspath(os.path.join(file_path, filename)))

        timedata = time.localtime(time.time())
        cndata = datetime(timedata[0], timedata[1], timedata[2], timedata[3], timedata[4], timedata[5])
        central = pytz.timezone('Asia/Shanghai')
        time_cn = central.localize(cndata)
        # time_result = str(time_cn.year).zfill(4) + '/' + str(time_cn.month).zfill(2) + '/' + \
        #               str(time_cn.day).zfill(2) + ' ' + \
        #               str(time_cn.hour).zfill(2) + ':' + str(time_cn.minute).zfill(2),

        subject = form['subject']
        group_name = form['group_name']
        student_name = form['student_name']
        try:
            student_id = int(form['student_id'])
        except ValueError:
            return make_alert('学号填写错误！')
        score = form['score']
        feedback = form['feedback']

        if group_name == '' or student_name == '' or subject == '' or score == '':
            return make_alert('表单填写错误，请重新填写。')

        if db.check_student_info(student_name, student_id) is False:
            return make_alert('学号和名字不匹配！')

        time_date = str(time_cn.year).zfill(4) + '/' + str(time_cn.month).zfill(2) + '/' + str(time_cn.day).zfill(2)
        file_key = "%s/%s/%s/%s.%s" % (time_date, subject, group_name, student_name, file_type)
        file_url = get_upload_prefix() + file_key
        submit_time = int(time.time())
        # print(file_key)
        upload_file_threaded(file_key, filedata)

        db.new_submit(group_name, student_name, student_id, subject, score, file_url, feedback, submit_time)

        return make_alert('上传成功启动，可以关闭网页。请等待服务器CDN缓存(约30秒，视文件大小而定)')


@app.route('/data', methods=["GET", "POST"])
def show_data():
    # form = request.form
    if request.method == 'GET':
        args0 = dict(request.args)
        args = {}
        for arg in args0:
            val = args0[arg]
            if type(val) is list:
                args[arg] = val[0]
            else:
                args[arg] = val
        # print(args)
        timedata = time.localtime(time.time())
        # print(timedata)
        year = int(timedata[0])
        cndata = datetime(timedata[0], timedata[1], timedata[2], timedata[3], timedata[4], timedata[5])
        central = pytz.timezone('Asia/Shanghai')
        time_cn = central.localize(cndata)
        if 'subject' in args:
            subject = args['subject']
        else:
            subject = 'all'
        if 'start_date' in args:
            start_date = args['start_date']
        else:
            start_date = 'all'
        if 'end_date' in args:
            end_date = args['end_date']
        else:
            end_date = 'all'
        if 'start_month' in args:
            start_month = args['start_month']
        else:
            start_month = 'all'
        if 'end_month' in args:
            end_month = args['end_month']
        else:
            end_month = 'all'
        if start_month == 'all' or start_date == 'all':
            start_time_utc = None
        else:
            start_date, start_month = int(start_date), int(start_month)
            start_time_utc = int(datetime(year=year, month=start_month, day=start_date).timestamp())
        if end_month == 'all' or end_date == 'all':
            end_time_utc = None
        else:
            end_date, end_month = int(end_date), int(end_month)
            end_time_utc = int(datetime(year=year, month=end_month, day=end_date+1).timestamp())
        time_limit = ''
        if start_time_utc is None and end_time_utc is None:
            time_limit = ''
        elif start_time_utc is None and start_time_utc is not None:
            time_limit = 'submit_time <= %s' % end_time_utc
        elif start_time_utc is not None and end_time_utc is None:
            time_limit = 'submit_time >= %s' % start_time_utc
        elif start_time_utc is not None and end_time_utc is not None:
            time_limit = '%s <= submit_time AND submit_time <= %s' % (start_time_utc, end_time_utc)
        # print('time_limit:', time_limit, start_time_utc, end_time_utc)

        if 'group_name' in args:
            group_name = args['group_name']
        else:
            group_name = 'all'

        if 'conclude' in args:
            conclude = args['conclude']
            # print(conclude, type(conclude))
            if conclude == 'True':
                conclude = True
            else:
                conclude = False
        else:
            conclude = True
        # print(type(conclude))

        if subject == 'all':
            subject_to_limit = '%'
        else:
            subject_to_limit = subject
        if group_name == 'all':
            group_name_to_limit = '%'
        else:
            group_name_to_limit = group_name

        if 'download' in args:
            download = args['download']
            if download == 'True':
                download = True
            else:
                download = False
        else:
            download = False

        if time_limit != '':
            limit = "%s AND subject LIKE '%s' AND group_name LIKE '%s'" % \
                    (time_limit, subject_to_limit, group_name_to_limit)
        else:
            limit = "subject LIKE '%s' AND group_name LIKE '%s'" % \
                    (subject_to_limit, group_name_to_limit)

        # print(limit)

        known_urls = []

        # if g_debug is False and ('login' not in session or session['login'] is False):
        #     return render_template('input_password.html', cdn=cdn)
        data = db.get_raw_data(limit_str=limit)
        #     0          1          2          3       4       5         6          7
        # group_name, student, student_id, subject, score, file_url, feedback, submit_time
        #           0         1       2       3       4        5     6       7

        if conclude is False:
            labels = ['学科', '提交日期', '组长', '学号', '姓名', '分数', '反馈', '文件']
            # 整理数据
            results = []
            for d in data:
                # print(d)
                r = ['' for _ in range(8)]
                timedata2 = time.localtime(int(d[7]))
                cndata2 = datetime(timedata2[0], timedata2[1], timedata2[2], timedata2[3], timedata2[4], timedata2[5])
                central2 = pytz.timezone('Asia/Shanghai')
                time_you = central2.localize(cndata2)
                r[1] = "%s/%s" % (time_you.month, time_you.day)
                r[2] = d[0]
                r[3] = d[2]
                r[4] = d[1]
                r[0] = d[3]
                r[5] = d[4]
                r[6] = d[6]
                r[7] = d[5]
                known_urls.append(r[7])
                results.append(copy.deepcopy(r))

        else:  # conclude
            labels = ['组长', '学号', '姓名', '语文', '数学', '英语', '物理', '化学', '生物']
            # subject_label = ['语文', '数学', '英语', '物理', '化学', '生物']
            subject_label_re = {'语文': 0, '数学': 1, '英语': 2, '物理': 3, '化学': 4, '生物': 5}
            # labels2 = ['学科', '提交日期', '组长', '学号', '姓名', '分数', '反馈', '文件']
            students_info_raw = list(db.get_students_data())
            students_info_raw.sort(key=lambda x: int(x[0]))
            # print(students_info_raw)
            students_name_id = {}
            students_id_name = {}
            students_group = {}
            for student in students_info_raw:
                students_name_id[student[1]] = int(student[0])
                students_id_name[int(student[0])] = str(student[1])
                if student[1] not in students_group:
                    student_group = db.get_students_group(student[1])
                    # print(student_group)
                    if len(student_group) == 0:
                        students_group[student[1]] = '未知'
                        continue
                    students_group[student[1]] = str(student_group[0][0])
            # print(students_group)
            # 整理数据
            results = []
            results_dict = {}
            for stu in students_info_raw:
                results_dict[stu[1]] = [students_group[stu[1]], stu[0], stu[1], 0, 0, 0, 0, 0, 0]
            # print(results)
            for d in data:
                # print(d)
                #     0          1          2          3       4       5         6          7
                # group_name, student, student_id, subject, score, file_url, feedback, submit_time
                #           0         1       2       3       4        5     6       7
                # r = ['' for i in range(8)]
                # timedata2 = time.localtime(int(d[7]))
                # cndata2 = datetime(timedata2[0], timedata2[1], timedata2[2], timedata2[3], timedata2[4], timedata2[5])
                # central2 = pytz.timezone('Asia/Shanghai')
                # time_you = central2.localize(cndata2)
                # r[1] = "%s/%s" % (time_you.month, time_you.day)
                # r[2] = d[0]
                # r[3] = d[2]
                # r[4] = d[1]
                # r[0] = d[3]
                # r[5] = d[4]
                # r[6] = d[6]
                # r[7] = d[5]
                results_dict[d[1]][subject_label_re[d[3]] + 3] = d[4]

                # results.append(copy.deepcopy(r))
            for r in results_dict:
                val = results_dict[r]
                if group_name != 'all' and val[0] == group_name:
                    results.append(val)
                if group_name == 'all':
                    results.append(val)
                # print(group_name, val)

            results.sort(key=lambda x: x[1])

            # return ''

        groups = db.get_group_list()
        
        download_url = '/data?download=True&start_month=%s&start_date=%s&end_month=%s&' \
                       'end_date=%s&group_name=%s&subject=%s&conclude=%s' % \
                       (start_month, start_date, end_month, end_date, group_name, subject, conclude)

        if download is True:
            # 生成csv文件
            csv_text = ''
            for label in labels:
                csv_text += label + ','
            # 去掉,
            csv_text = csv_text[:-1]
            csv_text += '\n'
            for r in results:
                for p in r:
                    csv_text += str(p) + ','
                csv_text = csv_text[:-1] + '\n'
            csv_file = csv_text.encode('gbk', errors='ignore')
            csv_data = io.BytesIO()
            csv_data.write(csv_file)
            csv_data.seek(0)
            # filename_ = ("1702约考成绩导出数据(下载于%s-%s-%s).csv" %
            #              (time_cn.year, time_cn.month, time_cn.day)).encode().decode('latin-1')

            # 保存为xlsx格式
            xlsx_data = io.BytesIO(csv_to_xlsx(csv_text))
            filename_ = ("1702约考成绩导出数据(下载于%s-%s-%s).xlsx" %
                         (time_cn.year, time_cn.month, time_cn.day)).encode().decode('latin-1')
            # response = make_response(send_file(csv_data, attachment_filename="%s" % filename_))
            response = make_response(send_file(xlsx_data, attachment_filename="%s" % filename_))
            response.headers["Content-Disposition"] = "attachment; filename=%s;" % filename_
            return response

        return render_template('data_show.html', content=results, labels=labels,
                               cdn=cdn, start_month=start_month, start_date=start_date,
                               end_month=end_month, end_date=end_date, selected_subject=subject,
                               selected_group_name=group_name, group_names=groups, download_url=download_url,
                               conclude=conclude, known_urls=known_urls)
    return 'Error.'


@app.route('/hello')
def hello():
    return render_template('data_show.html', labels=['A', 'B'], content=[[1, 2], [3, 4]])


@app.route('/captcha/<string:cid>')
def captcha_get_img(cid: str):
    # print(cid)
    return redirect(url_for('static', filename='captcha/%s.jpg' % cid))


@app.route('/res/<string:filename>')
def res(filename: str):
    return redirect(url_for('static', filename=filename))


@app.route('/admin', methods=['POST', 'GET'])
def admin():
    form = request.form
    if request.method == 'POST':
        # if 'password' in form and 'character' in form:
        #     password = form['password']
        #     character = form['character']
        #     if password == 'ltyz13579':
        #         session['character'] = character
        #         return '<a href="/data">返回上一页</a>'
        #     else:
        #         return '密码错误！ <a href="/data">返回上一页</a>'
        if 'password' in form:
            password = form['password']
            if password == 'ltyz13579':
                session['login'] = True
                return redirect('/admin')
            else:
                return '%s<a href="/data">返回上一页</a>' % make_alert('密码错误！')
        return '%s<a href="/data">返回上一页</a>' % make_alert('提交错误！')
    if 'login' not in session or session['login'] is not True:
        return render_template('input_password3.html', cdn=cdn)
    return render_template('admin.html')


@app.route('/debug_clear_all')
def clear_all():
    if 'login' not in session or session['login'] is not True:
        return redirect('/admin')
    if db.sql_type == db.sql_types['SQLite']:
        try:
            db.db_backup()
        except sqlite3.OperationalError as e:
            return make_alert('错误。%s' % str(e))
    else:
        try:
            db.db_backup()
        except psycopg2.errors.UndefinedTable as e:
            return make_alert('错误。%s' % str(e))
    db.db_init()
    return make_alert('OK.')


@app.route('/update_stu_info', methods=['GET', 'POST'])
def update_stu_info():
    if request.method == 'GET':
        if 'login' not in session:
            return render_template('input_password2.html', cdn=cdn)
        return render_template('upload_stu_info.html')
    else:
        # POST
        if 'password' in request.form:
            if request.form['password'] != 'ltyz13579':
                return make_alert('密码错误~') + '<a href="/update_stu_info">返回上一页</a>'
            return redirect('/update_stu_info')
        if 'file' not in request.files:
            return make_alert('没有选择文件。')
        file = request.files['file']
        if file.filename == '':
            return make_alert('没有选择文件。')
        filename = str(file.filename)
        file_type = filename.split('.')[-1].lower()
        if file_type not in ['csv', 'xls', 'xlsx']:
            return make_alert('文件类型错误！')
        filedata = io.BytesIO()
        file.save(filedata)
        filedata.seek(0)
        if file_type == 'csv':
            csv_data = filedata.read()
        else:
            csv_data = xlsx_to_csv(filedata.read()).encode()
        try:
            csv_data = csv_data.decode('gbk')
        except UnicodeDecodeError:
            try:
                csv_data = csv_data.decode('utf8')
            except UnicodeDecodeError:
                return make_alert('文件内容解码错误！')

        result = db.update_student_info(csv_data)
        if result is False:
            return make_alert('文件解析错误！') + '<a href="/update_stu_info">返回</a>'
        return redirect('/data')


@app.route('/favicon.ico')
def icon():
    return redirect('https://s.gravatar.com/avatar/544b5009873b27f5e0aa6dd8ffc1d3d8?s=144')


if __name__ == '__main__':
    _li = os.listdir('tmp/captcha')
    for _i in _li:
        # if _i != '.nomedia':
        if '.jpg' in _i:
            os.remove('tmp/captcha/%s' % _i)
    app.run('0.0.0.0', port=os.getenv("PORT", "5000"), debug=False)
    # captcha_get("12 + 32").show()

