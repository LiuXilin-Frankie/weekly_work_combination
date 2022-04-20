import datetime
import requests
import numpy as np
from tqdm import tqdm
import time
import os
import json
import re
from lxml import etree
from scrapy.selector import Selector


def generate_QA_page(response):
    """
    传入的response是获取到的html.text
    对获取到页面的内容进行拆分以及清理
    example:'黑马不黑|北汽蓝谷|希望全新版极狐展车和试驾车到店不要再偷偷摸摸的了，
            请从镇江工厂100辆hi版车一起出发，自动驾驶到全国各个4S店（配备安全员）。
            并视频每天分享。这活动不需要17个亿很省钱。\n'
    """
    response_list = response.split('m_feed_line')
    try:
        response_list = response_list[:-1] + response_list[-1].split('m_feed_comments')
    except:
        pass

    content_page = list()
    for res in response_list:
        AskQNameList = Selector(text=res).xpath("//div[@class='m_feed_detail']/div[1]/p/text()").extract()
        AskQueList = Selector(text=res).xpath("//div[@class='m_feed_detail']/div[2]/div[2]/text()").extract()
        AskTList = Selector(text=res).xpath("//div[@class='m_feed_detail']/div[2]/div[4]/div[2]/span/text()").extract()
        ReplyQList = Selector(text=res).xpath("//div[@class='m_feed_detail m_qa']/div[3]/div[2]/text()").extract()
        ReQTimeList = Selector(text=res).xpath("//div[@class='m_feed_detail m_qa']/div[4]/div[3]/span/text()").extract()

        #meaningless element since the split func
        if AskQNameList ==list():
            continue
            #pass

        #clean the content in elements
        AskQueList[0] = AskQueList[0].replace(':','')
        AskQueList[0] = AskQueList[0].replace('(','')
        AskQueList[1] = AskQueList[1].replace(')','')
        QA_detail = AskQNameList+AskQueList+AskTList+ReplyQList+ReQTimeList
        one_QA = QA_detail[0]
        for ele in QA_detail[1:]:
            one_QA = one_QA+'|'+ele

        # repeat cleaning
        if '\n' in one_QA:
            #if '\n' exist, needs special process
            one_QA = one_QA.replace('\n','')
        if '\r' in one_QA:
            #if '\n' exist, needs special process
            one_QA = one_QA.replace('\r','')
        if '\t' in one_QA:
            #if '\n' exist, needs special process
            one_QA = one_QA.replace('\t','')
        if ' ' in one_QA:
            #if '\n' exist, needs special process
            one_QA = one_QA.replace('\t','')
        content_page.append(one_QA+'\n')
    return content_page


def create_text(filename,mode=1):
    """
    无论您在何处运行该程序，该程序会在py文件的工作路径下创建sseinfo_company_QA文件夹并存储txt信息
    如果文件名已存在，会停止创建并在该文件下写入txt
    如果txt已经存在并且mode=1，则会覆盖成新的txt，否则只会return路径并不会覆写txt
    创建txt成功后，return新创建的txt的路径
    """
    path = os.getcwd()+"/sseinfo_company_QA/"
    if os.path.exists(path):
        pass
    else:
        os.mkdir(path)
        
    file_path = path + filename + '.txt'
    if os.path.exists(file_path):
        if mode==1:
            os.remove(file_path)
        else:
            return file_path
    f = open(file_path,'w',encoding="utf-8")
    f.close()
    return file_path


def duplicate_QA(QA_list):
    """
    该函数用于删除获取到的QAlist中重复的部分
    并且对其按照时间由近到远的排序
    """
    final_QA = list()
    
    for one_line in QA_list:
        index = False
        for temp in final_QA:
            if one_line in temp:
                index = True
        
        if index==True:
            continue
        final_QA.append(one_line)
    return final_QA


def get_QA(stock_code_list, time_stop=0.5, overwrite=True, look_forward_day=60):
    """
    ReturnType:
    生成关于每一个传入股票命名的txt文档，其中记录的是查询问答信息
    ArgType：
    stock_code_list为股票代码的数字部分组成的list，元素属性为int/str均可
    time_sleep为防止http被关闭设置的间隔时间
    overwrite为是否覆写，默认为True，生成的txt会替代之前的txt文档
            若是为False，则代表增量爬取，同时新获取的增量内容会与旧内容合并写入
            程序会自动判断新内容与就内容之间的重复部分并以新内容为准，删除旧内容中的重复部分
    look_forward_day参数仅在overwrite==False时有效，为增量爬取向前看的天数
    PS：
    由于程序设置了重复出现检验的功能，并且由于网站问答内容的特殊性
    强烈建议look_forward_day大于上一次查询时的间隔，并且不小于30
    事实上，除了少部分波动较大的股票外，100以内的设置都不会对程序造成额外的负担
    """
    start_date = "2016-01-01"
    end_date = time.strftime("%Y-%m-%d", time.localtime())
    end_date = '2022-01-01'    #for test
    if overwrite==False:
        st_date = datetime.datetime.now() - datetime.timedelta(days =look_forward_day)
        start_date = st_date.strftime("%Y-%m-%d") 
        end_date = time.strftime("%Y-%m-%d", time.localtime())

    for code_name in tqdm(stock_code_list):
        code_name = int(code_name)
        stock_code = str(code_name)
        #因为页面不会返回总条数以及总页数
        #只能进行whlie循环并在页面不再出现内容后跳出循环
        page_number = 1
        content_add = list()
        while True:
            url = "http://sns.sseinfo.com/qasearch.do"
            #无法调整page_size，只能一次回传10个慢慢来
            params = {
                "keyword": code_name,
                "sdate":start_date,
                "edate":end_date,
                "page":page_number,
                }
            res = requests.get(url,params=params)
            response = res.text
            if "暂时没有内容" in response:
                break
            content_page = generate_QA_page(response)
            for one_QA in content_page:
                content_add.append(one_QA)
            
            page_number += 1
            time.sleep(time_stop)
        
        #开始进行问答的txt写入工作。
        if overwrite==True:
            file_path = create_text(stock_code)
            with open(file_path,"w",encoding="utf-8") as f:
                for lines in content_add:
                    f.write(lines)
        elif overwrite==False:
            file_path = create_text(stock_code,mode=2)
            original_content = list()
            with open(file_path,"r",encoding="utf-8") as f:
                for lines in f.readlines():
                    original_content.append(lines)

            #将两部分内容叠加，新查询的内容在前
            #在之后的重复查询中，新的内容会被保留
            for one_QA in original_content:
                content_add.append(one_QA)
            content_add = duplicate_QA(content_add)

            #因为已经对旧查询的内容读取，所以这里删除原txt重新覆写提升冗余性。
            file_path = create_text(stock_code)
            with open(file_path,"w",encoding="utf-8") as f:
                for lines in content_add:
                    f.write(lines)
    
    
    

if __name__ == "__main__":
    stock_query_list = ["600733",
                        "603025",
                        "600073"]
    #for test
    #先运行overwrite=True的get_QA函数以初始化创建文档
    #(记得更改get_QA中关于end_date的测试，使end_date不为今天)
    #再运行overwrite=False的get_QA函数做增量查询
    #get_QA(stock_query_list, time_stop=1)
    get_QA(stock_query_list, overwrite=False, time_stop=1, look_forward_day=120)
    print('/*----- misson successed! -----*/')