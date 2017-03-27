# -*- coding: utf-8 -*-
#import urllib
import urllib2
import json
import time
import MySQLdb
import threading
import re
#from email.mime.multipart import MIMEMultipart
#from email.mime.base import MIMEBase
#from email.mime.text import MIMEText
#from email.utils import COMMASPACE,formatdate
#from email import encoders
#from email.header import Header

#import os

import sys
reload(sys)
sys.setdefaultencoding('utf8')

custom_header = {"User-Agent" : "tvm-monitor"}
monitor_interface = "http://%s/approve/monitor"
max_threads = 10
started_thread = 0
http_timeout = 10
mysql_info = {"host": '10.10.10.10', "user": "monitor", "passwd": "111", "db": "livemonitor", "charset": "utf8"}


class Mysql:
    conn = ''
    cursor = ''

    def __init__(self, _host='localhost', _user='root', _password='123456', _db='test', _charset='utf8'):
        try:
            self.user = _user
            self.host = _host
            self.passwd = _password
            self.db = _db
            self.charset = _charset
            self.conn = MySQLdb.connect(user=self.user, host=self.host, passwd=self.passwd, db=self.db)
        except Exception, e:
            print e
            sys.exit()

        #防止中文乱码或报错.
        self.conn.set_character_set('utf8')
        self.cursor = self.conn.cursor()
        self.query('SET NAMES %s ' % self.charset)

    def query(self, sql):
        return self.cursor.execute(sql)

    def show(self):
        return self.cursor.fetchall()

    def showfirst(self):
        return self.cursor.fetchone()

    def __del__(self):
        if self.cursor != '':
            self.cursor.close()
        if self.conn != '':
            #由于MySQLdb模块会关闭自动提交,所以在关闭连接以前提交一下,否则数据库是没数据的.
            self.conn.commit()
            self.conn.close()


class Httphelper:
    def __init__(self, _custom_header):
        self.add_header = _custom_header

    def geturl(self, _url, _timeout):
        try:
            request = urllib2.Request(url=_url, headers=self.add_header)
            response = urllib2.urlopen(request, timeout=_timeout)
            return response.read()
        except urllib2.HTTPError, e:
            print e.code
        except urllib2.URLError, e:
            print "Error Reason:", e.reason
        return None


def getnodes():
    try:
        nodes_list = []
        mysql = Mysql(mysql_info["host"], mysql_info["user"], mysql_info["passwd"], mysql_info["db"], mysql_info["charset"])
        mysql.query("select id, nodeip from nodes_info where is_check >0;")
        nodes = mysql.show()
        for node in nodes:
            nodes_list.append({node[1]: node[0]})
        return nodes_list
    except Exception, ex:
        print ex
        return None


def docheck(_node):
    global started_thread
    msg = ''
    ip = _node.keys()[0]
    ipid = _node.get(ip)
    check_time = int(time.time())
    try:
        try:
            url = monitor_interface % ip
            myhttp = Httphelper(custom_header)
            gotdata = myhttp.geturl(url, http_timeout)
            if len(gotdata) > 0:
                try:
                    json_channels = json.loads(gotdata, encoding='utf-8')['data']
                    for (channel, statuses) in json_channels.items():
                        match = re.match(r'T.*', channel)
                        #过滤掉盒子采集频道
                        if match and len(channel) == 13:
                            continue
                        #match = re.match('ra.*', channel)
                        #if match:
                        #    continue
                        for(bote, delay_time) in statuses.items():
                            if delay_time == 86400:
                                msg += channel + ":" + bote + ":下载失败.|"
                            elif delay_time > 0:
                                msg += channel + ":" + bote + ":" + str(delay_time) + "|"
                    if len(msg) < 1:
                        msg = "所有频道检测正常."
                    else:
                        msg += "其他频道检测正常."
                except Exception, ex:
                    msg = ex
            else:
                msg = "本次检测结果获取接口内容为空,可能服务有问题或者超时了."
        except Exception, e:
            print e
            msg = e
        try:
            mysql = Mysql(mysql_info["host"], mysql_info["user"], mysql_info["passwd"], mysql_info["db"], mysql_info["charset"])
            sql = "insert into `checklog` (ip, checkstatus, checktime, node_id) values ('%s', '%s', %d, %d);" % (ip, msg, check_time, ipid)
            mysql.query(sql)
        except Exception, em:
            print em
    except Exception, ee:
        pass
    finally:
        started_thread -= 1


def checkstatus(_nodes_list):
    global started_thread
    for node in _nodes_list:
        t = threading.Thread(target=docheck, args=(node,))
        t.setDaemon(True)
        t.start()
        started_thread += 1
        while started_thread >= max_threads:
            time.sleep(1)

if __name__ == '__main__':
    nodes_list = getnodes()
    if nodes_list:
        checkstatus(nodes_list)
    while started_thread > 0:
        time.sleep(1)

