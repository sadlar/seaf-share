#!/usr/bin/env python

import httplib
import re
import getpass
import urllib
from clint.textui import progress
import requests
import os
import sys
import json
from requests_toolbelt import MultipartEncoder, MultipartEncoderMonitor

def downfile(url, path, name, headers):
    r = requests.get(url, stream=True, headers=headers)
    print path+"/"+name
    try:
        with open(path+"/"+name, 'wb') as f:
            total_length = int(r.headers.get('content-length'))
            for chunk in progress.bar(r.iter_content(chunk_size=1024), expected_size=(total_length/1024) + 1): 
                if chunk:
                    f.write(chunk)
                    f.flush()
    except Exception as e:
        print e
        print "url: "+url
        print "path: "+path
        print "name: "+name
        print headers

def downlist(files, set_headers, conn, connectPath, downpath, baseURL):
    for (t1, t2) in files:
        if t1[-9:-1] == "mode=lis":
            #print t2+" is a dir"
            conn.request(method = "GET", url = connectPath+t1, headers = set_headers)
            ret = conn.getresponse()
            resp = ret.read()
            subfiles = re.findall(r'<td>\W*a.*href="([^"]*)".*>(.*)</a>\W*</td>', resp, re.I)
            
            if os.path.exists(downpath+"/"+t2) == False:
                os.mkdir(downpath+"/"+t2)
            #print "dir: "+downpath+"/"+t2
            downlist(subfiles, set_headers, conn, connectPath, downpath+"/"+t2, baseURL)            
        else:
            #print t2+" is a file"
            #print t1
            #print "down: "+baseURL+t1+"&dl=1"
            downfile(baseURL+t1+"&dl=1", downpath, t2, set_headers)
            
def usage():
    print "seaf-share.py [get|put] [http|https]://share_url directory"
    
def  parseURL(url):
    ret = {};
    #print url[0:8]
    if url[0:8] == "https://":
        ret["connectProtocol"] = "https"
        ret["connectPort"] = 443;
        ret["connectURL"] = url[8:].split('/')[0]
        ret['connectPath'] = url[8+len(ret["connectURL"]):]
        if ret['connectPath'][-1] != '/':
            ret['connectPath'] = ret['connectPath']+'/'
    elif url[0:7] == "http://":
        ret["connectProtocol"] = "http"
        ret["connectPort"] = 80; 
        ret["connectURL"] = url[7:].split('/')[0]
        ret['connectPath'] = url[7+len(ret["connectURL"]):]
        if ret['connectPath'][-1] != '/':
            ret['connectPath'] = ret['connectPath']+'/'
    else:
        ret = -1
    return ret

def connectServer(serverInfo):
    if serverInfo["connectProtocol"] == "https":
        conn = httplib.HTTPSConnection(host = serverInfo["connectURL"], port = serverInfo["connectPort"])
    elif serverInfo["connectProtocol"] == "http":
        conn = httplib.HTTPConnection(host = serverInfo["connectURL"], port = serverInfo["connectPort"])    
    else:
        raise Exception('connectProtocol http/https')
    return conn

def login(conn, serverInfo, csrf, pwd):
    set_params = urllib.urlencode({'csrfmiddlewaretoken': csrf, 'password': pwd})
    set_headers = {"Content-type": "application/x-www-form-urlencoded", 
               "Accept": "text/plain",
               "Cookie": "csrftoken="+csrf+"; ",
               "Referer": serverInfo["connectProtocol"]+"://"+serverInfo["connectURL"]+serverInfo["connectPath"]}

    conn.request(method = "POST", url = serverInfo["connectPath"], body = set_params, headers = set_headers)
    ret = conn.getresponse()
    resp = ret.read()
    ret_headers = ret.getheaders()
    for (t1, t2) in ret_headers:
        if t1 == 'set-cookie':
            cookie = t2
    #print cookie
    sessionid = re.findall('sessionid=(\w*);', cookie, re.I)
    if len(sessionid) == 0:
        sessionid = -1
    else:
        sessionid = sessionid[0]
    return sessionid


def checkPass(conn, serverInfo):
    conn.request(method = "GET", url = serverInfo["connectPath"])
    ret = conn.getresponse()
    resp = ret.read()

    reqpass = re.search(r'Please input the password', resp, re.I)
    csrfmiddlewaretoken = re.findall('csrfmiddlewaretoken. value=.(\w*)', resp, re.I)
    #print csrfmiddlewaretoken[0]
    
    ret = {}
    if reqpass:
        print "Password Required"
        pwd = getpass.getpass('password: ')
        #pwd = "12345678"
        #print pwd
        sessionid = login(conn, serverInfo, csrfmiddlewaretoken[0], pwd)
        if sessionid == -1:
            print "Verification fails"
            sys.exit()
        else:
            print "Verification successes"
            ret["csrf"] = csrfmiddlewaretoken[0]
            ret["sid"] = sessionid
    else:
        #print "not require password"
        ret["csrf"] = ""
        ret["sid"] = ""
        
    return ret

def getFile(resp, base_url, savePath, set_headers):
    filename = re.findall(r'<h2 class="ellipsis no-bold" title="(.*)">', resp, re.I)
    if len(filename) < 1:
        return False
    else:
        downfile(base_url+"?dl=1", savePath, filename[0], set_headers)
        return True

def getFiles(serverInfo, savePath):
    if os.path.isdir(savePath) == False:
        print "The saving path ("+savePath+") does not exist. Please specify a valid saving path."
        sys.exit()
    conn = connectServer(serverInfo)
    loginInfo = checkPass(conn, serverInfo)
    
    
    set_headers = {"Content-type": "application/x-www-form-urlencoded", 
               "Accept": "text/plain",
               "Cookie": "csrftoken="+loginInfo["csrf"]+"; sessionid="+loginInfo["sid"]+"; ",
               "Referer": serverInfo["connectProtocol"]+"://"+serverInfo["connectURL"]+serverInfo["connectPath"]}
    conn.request(method = "GET", url = serverInfo["connectPath"], headers = set_headers)
    ret = conn.getresponse()
    resp = ret.read()
    
    files = re.findall(r'<td>\W*a.*href="([^"]*)".*>(.*)</a>\W*</td>', resp, re.I)
    baseURL = serverInfo["connectProtocol"]+"://"+serverInfo["connectURL"]
    if len(files) < 1:
        if getFile(resp, baseURL+serverInfo["connectPath"], savePath, set_headers) == False:
            print "This is not a valid downloading share link."
        sys.exit()
    sharename = re.findall(r'<h2>(.*)</h2>', resp, re.I)
    downpath = str(savePath+"/"+sharename[0]).replace("//", "/")

    if os.path.exists(downpath) == False:
        os.mkdir(downpath)
    downlist(files, set_headers, conn, serverInfo["connectPath"], downpath, baseURL)

def getUploadLink(conn, uploadquery):
    set_headers = {"Accept": "application/json",
               "X-Requested-With": "XMLHttpRequest"}
    conn.request(method = "GET", url = uploadquery, headers = set_headers)
    ret = conn.getresponse()
    resp = ret.read()
    data = json.loads(resp)
    if 'url' in data:
        return data['url']
    else:
        return False

def create_callback(encoder_len):
    total_len = encoder_len
    bar = progress.Bar(expected_size=(total_len/1024)+1)
    def my_callback(monitor):
        # Your callback function
        if monitor == -1:
            bar.done()
        else:
            bar.show(monitor.bytes_read/1024+1)        
        #print str(monitor.bytes_read/1024)+" "+str(total_len/1024+1)
    return my_callback


def uploadFile(file_dir, file_name, upload_dir, posturl, parent_dir, set_headers):
    print "Uploading: "+str(file_dir+"/"+file_name).replace("//", "/")

    e = MultipartEncoder(fields={'filename': file_name,
                                 'file': (file_name, open(file_dir+"/"+file_name, 'rb'), 'text/plain'),
                                 'parent_dir': parent_dir,
                                 'relative_path': upload_dir})
    callback = create_callback(e.len)
    set_params = MultipartEncoderMonitor(e, callback)
    set_headers["Content-type"] = set_params.content_type 

    r = requests.post(posturl, data=set_params, headers=set_headers)
    #data = json.loads(r.content)
    callback(-1)
    
def uploadDir(upload_dir, posturl, parent_dir, base_dir, set_headers):
    dirlist = os.listdir(upload_dir)
    for f in dirlist:
        if os.path.isfile(upload_dir+"/"+f):
            uploadFile(upload_dir, f, base_dir, posturl, parent_dir, set_headers)
        elif os.path.isdir(upload_dir+"/"+f):
            uploadDir(upload_dir+"/"+f, posturl, parent_dir, base_dir+"/"+f, set_headers)

def putFiles(serverInfo, getPath):
    if os.path.exists(getPath) == False:
        print "The uploading target does not exist"
        sys.exit()
    conn = connectServer(serverInfo)
    loginInfo = checkPass(conn, serverInfo)
    
    set_headers = {"Content-type": "application/x-www-form-urlencoded", 
               "Accept": "text/plain",
               "Cookie": "csrftoken="+loginInfo["csrf"]+"; sessionid="+loginInfo["sid"]+"; ",
               "Referer": serverInfo["connectProtocol"]+"://"+serverInfo["connectURL"]+serverInfo["connectPath"]}
    conn.request(method = "GET", url = serverInfo["connectPath"], headers = set_headers)
    ret = conn.getresponse()
    resp = ret.read()
    uploadquery = re.findall(r"url: '(.*)',", resp, re.I)
    #print uploadquery[0]
    parent_dir = re.findall(r"'parent_dir': \"(.*)\",", resp, re.I)
    #print parent_dir[0]
    
    if len(uploadquery) < 1:
        print "This is not a valid uploading share link."
        sys.exit()
    uploadLink = getUploadLink(conn, uploadquery[0])
    if uploadLink == False:
        print "This is not a valid uploading share link."
        sys.exit()

    if os.path.isdir(getPath):
        uploadDir(getPath, uploadLink, parent_dir[0], os.path.basename(getPath), set_headers)
    elif os.path.isfile(getPath):
        uploadFile(os.path.dirname(getPath), os.path.basename(getPath), "", uploadLink, parent_dir[0], set_headers)


def main():
    if len(sys.argv) < 4:
        usage()
    elif sys.argv[1] == "get":
        ret = parseURL(sys.argv[2])
        if ret == -1:
            usage()
        else:
            savePath = os.path.abspath(sys.argv[3])
            getFiles(ret, savePath)
    elif sys.argv[1] == "put":
        ret = parseURL(sys.argv[2])
        if ret == -1:
            usage()
        else:
            uploadPath = os.path.abspath(sys.argv[3])
            putFiles(ret, uploadPath)
    else:
        usage()
    sys.exit();

if __name__ == "__main__": main()

    








