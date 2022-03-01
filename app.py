import os, datetime, random

import json
from werkzeug.utils import secure_filename
import pymysql
from flask import Flask, render_template, request, jsonify
from aip import AipFace

import json
import requests

from tencentcloud.common import credential
from tencentcloud.common.exception.tencent_cloud_sdk_exception import TencentCloudSDKException
# 导入对应产品模块的 client models。
from tencentcloud.common.profile.client_profile import ClientProfile
from tencentcloud.iai.v20180301 import iai_client, models
import base64


app = Flask(__name__)

#文件上传存放的文件夹, 值为非绝对路径时，相对于项目根目录
IMAGE_FOLDER  = 'static/photo/'

#生成无重复随机数
gen_rnd_filename = lambda :"%s%s" %(datetime.datetime.now().strftime('%Y%m%d%H%M%S'), str(random.randrange(1000, 10000)))
#文件名合法性验证
allowed_file = lambda filename: '.' in filename and filename.rsplit('.', 1)[1] in set(['png', 'jpg', 'jpeg', 'gif', 'bmp','gif','jfif'])

app.config.update(
    SECRET_KEY = os.urandom(24),
    # 上传文件夹
    UPLOAD_FOLDER = os.path.join(app.root_path, IMAGE_FOLDER),

    # 最大上传大小，当前16MB
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
)



#face照片上传
@app.route('/facephotoupload', methods=['POST','OPTIONS'])
def facephotoupload():
    res = dict(code=-1, msg=None)
    f = request.files.get('file')
    if f and allowed_file(f.filename):
        filename = secure_filename(gen_rnd_filename() + "." + f.filename.split('.')[-1])  # 随机命名
        # 自动创建上传文件夹
        print(filename)
        if not os.path.exists(app.config['UPLOAD_FOLDER']):
            os.makedirs(app.config['UPLOAD_FOLDER'])
        # 保存图片
        f.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
        imgUrl = "static/photo/"+filename
        print(imgUrl)
        res.update(code=0, data=dict(src=imgUrl))
    else:
        res.update(msg="Unsuccessfully obtained file or format is not allowed")

    return jsonify(res)

#---------------------------------------------------------------------------

# 获取token
# client_id 为官网获取的AK， client_secret 为官网获取的SK
def get_token(client_id, client_secret):
    url = "https://aip.baidubce.com/oauth/2.0/token?grant_type=client_credentials"
    params = {"client_id": client_id, "client_secret": client_secret}
    response = requests.get(url, params=params)
    resultJson = response.json()
    return resultJson['access_token']



#动物识别
@app.route('/animal',methods=['GET','POST'])
def animal():
    img_dir=request.form.get("imgurl")

    request_url = "https://aip.baidubce.com/rest/2.0/image-classify/v1/animal"

    # 二进制方式打开图片文件
    f = open(img_dir, 'rb')
    img = base64.b64encode(f.read())

    params = {"image": img}
    params = urllib.parse.urlencode(params).encode(encoding='UTF8')

    access_token = get_token("Lh5ulpbBjD7oPoL4GMPtOquL", "1Z0Silf8ZF9mLytPbyoDa72N6rxS8p2U")
    request_url = request_url + "?access_token=" + access_token

    headers = {'content-type': 'application/json'}
    content = requests.post(request_url, data=params, headers=headers).json()

    people = {}

    people["name"]=content["result"][0]["name"]
    people["similar"]=content["result"][0]["score"]

    return json.dumps(people,ensure_ascii=False)



# 根据图片名读取图片，并转换成base64
def read_photo(name):
    with open(name, 'rb') as f:
        base64_data = base64.b64encode(f.read())
        base64_code = base64_data.decode()
    return base64_code


# 调用百度的接口，实现融合图片
def face_fusion(token, template, target):
    url = 'https://aip.baidubce.com/rest/2.0/face/v1/merge'
    request_url = url + '?access_token=' + token
    params = {
        "image_template": {
            "image": template,
            "image_type": "BASE64",
            "quality_control": "NONE"
        },
        "image_target": {
            "image": target,
            "image_type": "BASE64",
            "quality_control": "NONE"
        },
        "merge_degree": "NORMAL"
    }
    params = json.dumps(params)
    headers = {'content-type': 'application/json'}
    result = requests.post(request_url, data=params, headers=headers).json()
    if result['error_code'] == 0:
        res = result["result"]["merge_image"]
        url=down_photo(res)
        print(url)
        return url
    else:
        print(str(result['error_code'])+result['error_msg'])

# 下载融合后图片
def down_photo(data):
    imagedata = base64.b64decode(data)
    downimgurl="static/photo/"+gen_rnd_filename() + "result.jpg"
    file = open(downimgurl, "wb")
    file.write(imagedata)
    return downimgurl


#人脸融合
@app.route('/faceunion',methods=['GET','POST'])
def faceunion():
    template=request.form.get("template")
    target = request.form.get("target")
    res = dict(code=-1, msg=None)
    template = read_photo(template)
    target = read_photo(target)
    token = get_token('QLI8c7xbaMFMUoD50PAG1E6Y', 'XazF3SzHVxDjK7g2LlZmEYasMgegcnWz')
    downurl=face_fusion(token, template, target)
    res.update(code=0, data=dict(src=downurl))
    print(jsonify(res))
    return jsonify(res)

""" 你的APPID，API_KEY和SECRET_KEY """
APP_ID = '23750865'
API_KEY = 'QLI8c7xbaMFMUoD50PAG1E6Y'
SECRET_KEY = 'XazF3SzHVxDjK7g2LlZmEYasMgegcnWz'


# 封装成函数，返回获取的client对象
def get_client(APP_ID, API_KEY, SECRET_KEY):
    """
    返回client对象
    :param APP_ID:
    :param API_KEY:
    :param SECRET_KEY:
    :return:
    """
    return AipFace(APP_ID, API_KEY, SECRET_KEY)

#人脸匹对
@app.route('/facecompare',methods=['GET','POST'])
def facecompare():
    template = request.form.get("template")
    target = request.form.get("target")
    res = dict(code=-1, msg=None)
    client = get_client(APP_ID, API_KEY, SECRET_KEY)
    result = client.match([
        {
            'image': str(base64.b64encode(open(template, 'rb').read()), 'utf-8'),
            'image_type': 'BASE64',
        },
        {
            'image': str(base64.b64encode(open(target, 'rb').read()), 'utf-8'),
            'image_type': 'BASE64',
        }
    ])

    if result['error_msg'] == 'SUCCESS':
        score = result['result']['score']
        result=""
        if score>60:
            result="照片相似度为："+str(score)+"基本确定是本人"
        else:
            result="照片相似度为：" + str(score) + "基本确定不是本人"
        res.update(code=0, data=dict(src=result))
        print(jsonify(res))
        return jsonify(res)
    else:
        print('错误信息：', result['error_msg'])
        res.update(code=0, data=dict(src=result['error_msg']))
        print(jsonify(res))
        return jsonify(res)

#人脸分析
@app.route('/faceide',methods=['GET','POST'])
def faceide():
    global json_data
    img_dir=request.form.get("imgurl")

    secretId = 'AKIDTnx404di9Qds5OxUvfFl7IIUpi4xKrfd'
    secretKey = 'zuIWaCewLg1qIbAzetysumU7MnSwFgv5'

    with open(img_dir, 'rb') as f:
        base64_data = base64.b64encode(f.read())
        base64_code = base64_data.decode()
    try:
        # 实例化一个客户端配置对象，可以指定超时时间等配置
        clientProfile = ClientProfile()
        clientProfile.signMethod = "TC3-HMAC-SHA256"  # 指定签名算法
        # 实例化一个认证对象，入参需要传入腾讯云账户 secretId，secretKey
        cred = credential.Credential(secretId, secretKey)
        client = iai_client.IaiClient(cred, "ap-guangzhou", clientProfile)
        # 实例化一个请求对象
        req = models.DetectFaceRequest()

        # 人脸检测参数
        req.MaxFaceNum = 1
        req.Image = base64_code
        req.NeedFaceAttributes = 1
        req.NeedQualityDetection = 0

        # 通过 client 对象调用想要访问的接口，需要传入请求对象
        resp = client.DetectFace(req)
        # 输出 JSON 格式的字符串回包
        json_data = resp.to_json_string()
    except TencentCloudSDKException as err:
        print(err)

    data = json.loads(json_data)

    data2 = data["FaceInfos"]
    data2 = str(data2)
    data3 = data2[1:-1].replace("'", "\"").replace("False", "\"False\"").replace("True", "\"True\"")

    data4 = json.loads(data3)

    face = data4["FaceAttributesInfo"]
    people = {}
    if face["Gender"] > 50:
        people["Gender"] = "男性"
    else:
        people["Gender"] = "女性"
    people["Age"] = face["Age"]
    if face["Expression"] > 50:
        people["smile"] = "大笑"
    else:
        people["smile"] = "微笑"
    if face["Glass"] == "False":
        people["Glass"] = "未戴眼镜"
    else:
        people["Glass"] = "戴眼镜"
    people["Beauty"] = face["Beauty"]
    if face["Hat"] == "False":
        people["Hat"] = "未戴帽子"
    else:
        people["Hat"] = "戴帽子"
    if face["Mask"] == "False":
        people["Mask"] = "未戴口罩"
    else:
        people["Mask"] = "戴口罩"
    hair = face["Hair"]

    strr = ""

    if hair["Bang"] == 0:
        strr = "有刘海"
    else:
        strr = "无刘海"

    if hair["Color"] == 0:
        strr = strr + "黑色"
    elif hair["Color"] == 1:
        strr = strr + "金色"
    elif hair["Color"] == 2:
        strr = strr + "棕色"
    elif hair["Color"] == 3:
        strr = strr + "灰白色"

    if hair["Length"] == 0:
        strr = strr + "光头"
    elif hair["Length"] == 1:
        strr = strr + "短发"
    elif hair["Length"] == 2:
        strr = strr + "中发"
    elif hair["Length"] == 3:
        strr = strr + "长发"
    elif hair["Length"] == 4:
        strr = strr + "绑发"

    people["Hair"] = strr

    if face["EyeOpen"] == "True":
        people["EyeOpen"] = "睁着眼"
    else:
        people["EyeOpen"] = "闭着眼"

    return json.dumps(people,ensure_ascii=False)


import urllib





@app.route('/')
def hello_world():
    return render_template('index.html')

@app.route('/tz_faceidentify')
def tz_faceidentify():
    return render_template('faceidentify.html')

@app.route('/tz_faceunion')
def tz_faceunion():
    return render_template('faceunion.html')

@app.route('/tz_facecompare')
def tz_facecompare():
    return render_template('facecompare.html')

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')
@app.route('/tz_animal')
def tz_animal():
    return render_template('animal.html')



if __name__ == '__main__':
    app.run(port=8888,debug=True)
