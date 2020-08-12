# -*- coding: utf-8 -*-
import scrapy
import re
import uuid
import http.client
import hashlib
import urllib
import random
import json
from datetime import datetime

class WikigoogleSpider(scrapy.Spider):

    name = 'wikigoogle'

    # 将q从fromLang语言翻译为toLang语言
    def translang(self, q, fromLang, toLang):
        # appid = '20200710000516601'  # 填写你的appid
        # secretKey = 'KRlb_boHYpzhYgL1JOxy'  # 填写你的密钥
        appid = '20200724000525701'  # 填写你的appid
        secretKey = 'soqkIOmIaKXVnM6cZ982'  # 填写你的密钥
        httpClient = None
        myurl = '/api/trans/vip/translate'  # 通用翻译API HTTP地址
        fromLang = fromLang  # 原文语种
        toLang = toLang  # 译文语种
        salt = random.randint(32768, 65536)
        q = q

        sign = appid + q + str(salt) + secretKey

        sign = hashlib.md5(sign.encode()).hexdigest()
        myurl = myurl + '?appid=' + appid + '&q=' + urllib.parse.quote(
            q) + '&from=' + fromLang + '&to=' + toLang + '&salt=' + str(salt) + '&sign=' + sign

        # 建立会话，返回结果
        try:
            httpClient = http.client.HTTPConnection('api.fanyi.baidu.com')
            httpClient.request('GET', myurl)
            # response是HTTPResponse对象
            response = httpClient.getresponse()
            result_all = response.read().decode("utf-8")
            result = json.loads(result_all)
            return result['trans_result'][0]['dst']
        except Exception as e:
            print(e)
        finally:
            if httpClient:
                httpClient.close()

    # 将 times 转为时间戳
    def transtime(self, times):
        a = times.count('年')
        b = times.count('月')
        c = times.count('日')

        if a > 0 and b > 0 and c > 0:
            s = re.search('[0-9]*年[0-9]*月[0-9]*日', times, re.S).group(0)
            curTime = datetime.strptime(s, "%Y年%m月%d日")
        elif a > 0 and b > 0:
            s = re.search('[0-9]*年[0-9]*月', times, re.S).group(0)
            curTime = datetime.strptime(s, "%Y年%m月")
        elif a > 0:
            s = re.search('[0-9]*年', times, re.S).group(0)
            curTime = datetime.strptime(s, "%Y年")

        strTime = curTime.strftime('%Y-%m-%d %H:%M:%S')
        utcTime1 = datetime.strptime(strTime, '%Y-%m-%d %H:%M:%S')
        # 这个时间之后为正 之前为负
        utcTime2 = datetime.strptime("1970-01-01 00:00:00", '%Y-%m-%d %H:%M:%S')
        metTime = utcTime1 - utcTime2  # 两个日期的 时间差
        timeStamp = metTime.days * 24 * 3600 + metTime.seconds  # 换算成秒数
        return timeStamp

    # 从json文件获取关键词和国家，拼接谷歌搜索URL
    def start_requests(self):
        with open('input.json', 'r', encoding='utf-8') as f:
            json_str = json.load(f)
            orgname = json_str['orgname']
            location = json_str['location']
            f.close()
        # orgname = '社会主义行动'
        for ch in orgname:#判断query语言,认为第一个字符为中文即为中文
            if u'\u4e00' <= ch <= u'\u9fff':
                lang = 'zh-hans'
                break
            elif u'\u0000' <= ch <= u'\u007F':
                lang = 'en'
                break
        urls = 'https://www.google.com.hk/search?q=%s&hl=%s'%(orgname,lang)
        meta = {'location':location}
        yield scrapy.http.FormRequest(urls, meta=meta, callback=self.parse, dont_filter=True, encoding='utf-8')

    # 获取组织维基百科URL，并将语言与链接传递给parse_dif1 函数
    def parse(self, response):
        next_main_url = 'https://www.google.com.hk/' #链接拼接主体
        flag = 0 #标记是否找到wiki链接
        selector = scrapy.Selector(response)
        my_text = selector.xpath('//div[@class="rc"]')
        for each in my_text:
            wiki_url = each.xpath('div[@class="r"]/a/@href').extract()[0]#谷歌搜索结果链接
            wiki_text = each.xpath('div[@class="r"]/a/h3/text()').extract()[0]#谷歌搜索结果主题
            if 'Wikipedia' in wiki_text:#判断是否为wiki页面
                flag = 1
                break
            if '维基百科' in wiki_text:
                flag = 2
                break
        if flag == 0 :#若当前页面没有wiki，挑转到下一页
            next = selector.xpath('// *[ @ id = "pnnext"]/@href').extract()[0]
            next_url = next_main_url + next
            yield scrapy.http.Request(next_url, callback=self.parse, dont_filter=True, encoding='utf-8')
        else:
            meta = {'flag': flag, 'url': wiki_url,'location': response.meta['location']}
            yield scrapy.http.FormRequest(wiki_url, meta=meta, callback=self.parse_dif1, dont_filter=True,
                                          encoding='utf-8')

    # 判断是否存在消歧义页面
    def parse_dif1(self,response):
        main_url = 'https://zh.wikipedia.org'
        selector = scrapy.Selector(response)
        wiki_url = selector.xpath('//*[@id="mw-content-text"]/div/div[1]/b/a/@href').extract()
        if len(wiki_url) != 0 : # 存在消歧义页面,进入parse_dif2进行消歧义
            wiki_url = wiki_url[0]
            wiki_url = main_url + wiki_url
            meta = {'flag': response.meta['flag'],'location': response.meta['location']}
            yield scrapy.http.FormRequest(wiki_url, meta=meta, callback=self.parse_dif2, dont_filter=True, encoding='utf-8')
        else : # 不存在消歧义页面 判断flag == 1 即为英文 可以直接进入parse_wiki进行信息爬取，否则进入parse_lang进行语言转换
            wiki_url = response.meta['url']
            meta = {'flag': response.meta['flag']}
            if response.meta['flag'] == 1 :
                yield scrapy.http.FormRequest(wiki_url, meta=meta, callback=self.parse_wiki, dont_filter=True, encoding='utf-8')
            else:
                yield scrapy.http.FormRequest(wiki_url, meta=meta, callback=self.parse_lang, dont_filter=True, encoding='utf-8')

    # 消歧义
    def parse_dif2(self,response):
        main_url = 'https://zh.wikipedia.org'
        selector = scrapy.Selector(response)
        text = selector.xpath('//*[@id="mw-content-text"]/div/ul/li')
        location = response.meta['location']
        meta = {'flag': response.meta['flag']}
        for each in text :
            wiki_url = each.xpath('a/@href').extract()[0]
            wiki_url = main_url + wiki_url
            wiki_text = each.xpath('a/text()').extract()[0]
            if wiki_text.count(location) > 0 :
                if response.meta['flag'] == 1:
                    yield scrapy.http.FormRequest(wiki_url, meta=meta, callback=self.parse_wiki, dont_filter=True,
                                                  encoding='utf-8')
                else:
                    yield scrapy.http.FormRequest(wiki_url, meta=meta, callback=self.parse_lang, dont_filter=True,
                                                  encoding='utf-8')

    # 可能会由于VPN 获取的页面会是繁体，因此将页面转换为简体
    def parse_lang(self,response):
        main_url = 'https://zh.wikipedia.org'
        selector = scrapy.Selector(response)
        wiki_url = selector.xpath('//*[@id="ca-varlang-3"]/a/@href').extract()[0]
        wiki_url = main_url+wiki_url
        meta = {'flag': response.meta['flag']}
        yield scrapy.http.FormRequest(wiki_url, meta = meta, callback=self.parse_wiki, dont_filter=True, encoding='utf-8')

    # 获取页面数据：目录+概要 暂未考虑不存在目录和概要的页面
    def parse_wiki(self,response) :
        re_h1 = re.compile('<.*?>', re.I)  # 去除<>
        re_h2 = re.compile('&#(.*?);', re.I)#去除[1]···
        re_h3 = re.compile('\n\n',re.I)#同时两个换行则去掉一个
        results_dict = {}

        selector = scrapy.Selector(response)
        UUID = str(uuid.uuid1())
        results_dict['_id'] = UUID
        Name = selector.xpath('//*[@id="firstHeading"]/text()').extract()[0]
        results_dict['Name'] = Name

        my_text1 = selector.xpath('//*[@id="toc"]/ul/li')  # 目录
        text_list = []
        for each in my_text1 :
            text = each.xpath('a/@href').extract()[0]
            text = text[1:]
            text_list.append(text)

        text = ','.join(text_list)
        text = self.translang(text, 'cht', 'zh')
        text_list1 = text.split('，')

        my_text = response.text
        for each in range(0,len(text_list)):
            text = re.search('id="'+text_list[each]+'">.*?(<p>(.*?)<h2>|<ul>(.*?)</ul>|<ol(.*?)</ol>)',my_text,re.S).group(1)
            if text_list1[each] == "外部链接" or text_list1[each] == "External_links" :
                link_list = text.splitlines()
                OutLink = []
                for ea in range(0,len(link_list)):
                    link = re.search('href="(.*?)"',link_list[ea],re.S).group(1)
                    text1 = re_h1.sub('', link_list[ea])  # 去除<>
                    text1  = re_h2.sub('', text1 )  # 去除[1]···
                    text1  = re_h3.sub('\n', text1 )
                    link_dict = {"OutName":text1,"URL":link}
                    OutLink.append(link_dict)
                results_dict[text_list1[each]] = OutLink
            else:
                text1 = re_h1.sub('', text)  # 去除<>
                text1 = re_h2.sub('', text1)  # 去除[1]···
                text1 = re_h3.sub('\n', text1)
                text1 = text1.strip()
                if response.meta['flag'] == 1 :
                    text1 = self.translang(text1, 'en', 'zh')
                results_dict[text_list1[each]] = text1

        my_text2 = selector.xpath('//*[@id="mw-content-text"]/div/table[position()<3]/tbody/tr')  # 概要

        for each in my_text2:
            text = each.xpath('*').extract()
            if len(text) == 2:
                text1 = re_h1.sub('', text[0])
                text1 = text1.strip()
                if text1.count('网站') > 0 or text1 == "Website" :
                    text2 = re.search('href="(.*?)"', text[1], re.S).group(1)
                elif text1.count('成立') > 0 or text1 == "Formation" :
                    text2 = re_h1.sub('', text[1])
                    text2 = text2.strip()
                    if response.meta['flag'] == 1:
                        text2 = self.translang(text2,'en','zh')
                    text2 = self.transtime(text2)
                else:
                    text2 = re_h1.sub('', text[1])
                    text2 = text2.strip()
                    if response.meta['flag'] == 1:
                        text2 = self.translang(text2,'en','zh')
                if text1 != '':
                    results_dict[text1] = text2

        with open('results.json', 'w', encoding='utf-8') as f:
            json.dump(results_dict, f, indent=4, ensure_ascii=False)
            f.close()

