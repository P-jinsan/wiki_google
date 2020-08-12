from flask import Flask, json,request,Response
import time
import subprocess

app = Flask(__name__)  # 实例化flask app

# http://localhost/search?orgname=CIGI&&location=USA
@app.route('/search', methods=['GET'])
def input_read_json():

    # 把参数存入字典，之后写入json文件 用于爬虫读取数据
    input_dict = {}
    input_dict['orgname'] = request.args.get('orgname')
    input_dict['location'] = request.args.get('location')

    # 写入参数
    with open('input.json', 'w', encoding='utf-8') as f:
        json.dump(input_dict, f, indent=4, ensure_ascii=False)
        f.close()

    # 运行爬虫
    subprocess.Popen("scrapy crawl wikigoogle")
    time.sleep(10)

    # 读取爬虫获取的数据results
    with open('results.json', 'r', encoding='utf-8') as f:
        jsonStr = json.load(f)
        jsonStr = json.dumps(jsonStr,ensure_ascii=False,indent=4)
        return Response(jsonStr, mimetype='application/json')
        f.close()

if __name__ == '__main__':
    app.run(debug=False, host='localhost', port=80)



