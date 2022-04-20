import datetime
import requests
import numpy as np
from tqdm import tqdm
import time
import os


def txt_one_line(i):
    """
    该函数用于生成每一行txt content
    stock_code|secid|companyShortName|indexId|trade|pubDate|author_id|attachedPubDate|score|topStatus|Q_content|A_content
    忽略了数据中 esId|contentType|companyLogo|boardType|authorName|pubClient|attachedAuthor

    sample:000661|gssz0000661|长春高新|['制造业']|2022-02-16 16:32:56|911717249485619200|2022-02-17 21:43:39|0.0|0|你好,
           如果水针全面集采后,销量大增,请问公司目前厂区的产能跟得上吗?|您好,公司积极根据行业发展、公司战略规划、
           产品销售需求及预期等推动相关产能建设;同时相关集采相关招投标工作目前尚未实施完毕,对公司的影响和影响程度尚未确定。谢谢!

    如果问题没有被回答，仍然会被爬取并记录
    """
    contentlist = list()
    contentlist.append(i['secid'])
    contentlist.append(i['companyShortName'])
    contentlist.append(i['indexId'])
    contentlist.append(i['trade'])
    contentlist.append(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(i['pubDate'])*0.001)))
    contentlist.append(i['author'])
    try:
        # 如果问题没有被回答，则该段内容不会被记录
        contentlist.append(time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(int(i['attachedPubDate'])*0.001)))
        contentlist.append(i['score'])
        contentlist.append(i['topStatus'])
        contentlist.append(i['mainContent'])
        contentlist.append(i['attachedContent'])
    except:
        contentlist.append(i['mainContent'])   
        #没被回答的情况下仅仅记录问题的原文
    one_QA = str(i['stockCode'])
    for col in contentlist:
        one_QA = one_QA + '|' +str(col)
    
    return one_QA


def create_text(filename,mode=1):
    """
    无论您在何处运行该程序，该程序会在py文件的工作路径下创建irm_company_QA文件夹并存储txt信息
    如果文件名已存在，会停止创建并在该文件下写入txt
    如果txt已经存在并且mode=1，则会覆盖成新的txt，否则只会return路径并不会覆写txt
    创建txt成功后，return新创建的txt的路径
    """
    path = os.getcwd()+"/irm_company_QA/"
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


def query_stock_name(stock_code_list=None,time_stop=0.2):
    '''
    这个函数用于获取股票在irm网站下的对应名称，如000661：gssz000661_000661 or 000333：9900005965_000333 or 002432：9900012876_002432
    作者并没有发现任何规律只能一次次查询,为防止IP被封，函数设置了time_stop参数
    可以通过从外部传入需要的股票字段stock_code_list来加速查询，否则，函数会遍历13000个整数查询（因为无法获取股票是否正在被交易）
    stock_code_list为list，sample:['000661','000001']，其中的元素可以为int也可以为str。但是仅包括股票代码的数字部分
    return的stock_query_list是所有要查询的股票在irm网站中对应的名称。
    '''

    stock_query_list = list()
    url = 'http://irm.cninfo.com.cn/ircs/index/queryKeyboardInfo'
    if stock_code_list==None:
        stock_code_list = list(range(1,4500)) +list(range(300000,301500)) +list(range(600000,606000)) +list(range(688000,689300))

    for stock_code in tqdm(stock_code_list):
        params = {'keyWord': str(stock_code)}
        res = requests.post(url,params=params)
        contentthispage = res.json()
        try:
            data = contentthispage['data'][0]
            stock_in_irm = str(data['secid'])+'_'+str(data['stockCode'])
            if stock_in_irm in stock_query_list:
                continue
            stock_query_list.append(stock_in_irm)
        except:
            pass
        time.sleep(time_stop)
    #Infomation will be stored in one txt file which means you just run once in a long period.
    return stock_query_list


def duplicate_QA(QA_list):
    """
    该函数用于删除获取到的QAlist中重复的部分
    并且对其按照时间由近到远的排序
    """
    index_list = list()
    temp_QA = list()
    for num in range(len(QA_list)):
        item = QA_list[num]
        one_QA = item.split('|')
        QA_index = int(one_QA[3])
        if QA_index in index_list:
            continue
        index_list.append(QA_index)
        temp_QA.append(item)
    mask = sorted(range(len(index_list)), key=lambda k:index_list[k],reverse=True)
    final_QA = list()
    for index in mask:
        final_QA.append(temp_QA[index])
    return final_QA


def get_QA(stock_query_list, time_stop=0.2, overwrite=True, look_forward_day=60):
    """
    ReturnType:
    生成关于每一个传入股票命名的txt文档，其中记录的是查询问答信息
    ArgType：
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
    #end_date = '2022-01-31'    #for test
    if overwrite==False:
        st_date = datetime.datetime.now() - datetime.timedelta(days =look_forward_day)
        start_date = st_date.strftime("%Y-%m-%d") 
        end_date = time.strftime("%Y-%m-%d", time.localtime())

    for code_name in tqdm(stock_query_list):
        stock_code = code_name[-6:]
        url = "http://irm.cninfo.com.cn/ircs/search/searchResult?keywords=&infoTypes=1%2C11"
        params = {
            "stockCodes":code_name,
            "pageNum":1,
            "startDate":start_date+" 00:0000:00:00",
            "endDate":end_date+" 23:5923:59:59",
            "onlyAttentionCompany":2,
            "pageSize":1000
        }
        res = requests.get(url,params=params)
        contentthispage = res.json()
        totalRecord = contentthispage['totalRecord']
        totalPage = contentthispage['totalPage']

        if totalRecord==0:
            #如果搜索不到问答，仍然会创建txt文件，但是不会写入任何东西
            if overwrite==False:
                continue
            elif overwrite==True:
                file_path = create_text(stock_code)

        content_add = list()
        for page_num in range(totalPage):
            time.sleep(time_stop)
            params['pageNum'] = page_num+1
            res = requests.get(url,params=params)
            contentthispage = res.json()
            for i in contentthispage['results']:
                one_QA = str(txt_one_line(i))
                if '\n' in one_QA:
                    #if '\n' exist, needs special process
                    one_QA = one_QA.replace('\n','')
                if '\r' in one_QA:
                    #if '\n' exist, needs special process
                    one_QA = one_QA.replace('\r','')
                content_add.append(one_QA+'\n')
        time.sleep(time_stop)
        
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
    #stock_query_list = query_stock_name()
    stock_query_list = ['gssz0000001_000001',
                        'gssz0000002_000002',
                        'gssz0000023_000023',
                        'gssz0000004_000004',
                        '9900005965_000333',
                        '9900012876_002432']
    #for test
    #先运行overwrite=True的get_QA函数以初始化创建文档
    #(记得更改get_QA中关于end_date的测试，使end_date不为今天)
    #再运行overwrite=False的get_QA函数做增量查询
    #get_QA(stock_query_list)
    get_QA(stock_query_list, overwrite=False)
    print('/*----- misson successed! -----*/')
