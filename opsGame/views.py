#!/usr/bin/env python3
#  -*- endcoding=UTF-8 -*-

import time
import commands, json
from flask import request, session, url_for, json
from sqlalchemy import and_
from ansibleApi import runner
from opsGame import app, db
from flask import render_template
from opsGame.models import processMonitor,fileSystemMonitor, hosts, memoryMonitor
from opsGame.tools.tools import tool


# 传入inventory路径
inventoryPath = '/etc/ansible/Inventory/'
ansible = runner.ansibleRunner(inventoryPath)
# 读取的inventory文件夹设置信息
inventoryData = ansible.inventory
# k-v结构，k为组名，v为组内hostIP
group_kv_dict = inventoryData.groups
# k-v结构，kv 相同
host_kv_dict = inventoryData.hosts
# group 组名列表
group_k_list = list(group_kv_dict.keys())
# 主机IP列表
host_k_list = list(host_kv_dict.keys())
# 分组的个数
howManyGroups = len(group_k_list)
# 主机的个数
howManyHost = len(host_k_list)
# 执行命令次数
cmdCount = 0


# 获取监控参数
@app.route('/getargs/', methods=['get'])
def getArgs():

    alive = hosts.query.filter_by(status=1).count()
    argsData = {}
    argsData['groupList'] = group_k_list
    for group in group_k_list:
        argsData[group+'_on'] = hosts.query.filter(and_(hosts.status == 1, hosts.hostGroup == group)).count()
        offHost = hosts.query.filter(and_(hosts.status == 0, hosts.hostGroup == group)).all()
        hostList = []
        for host in offHost:
            hostList.append(host.hostIP)
        argsData[group + '_off_host'] = hostList
        argsData[group+'_off'] = hosts.query.filter(and_(hosts.status == 0, hosts.hostGroup == group)).count()
    argsData['cmdCount'] = cmdCount
    argsData['groupCount'] = howManyGroups - 2
    argsData['alive'] = alive
    argsData['offline'] = howManyHost - alive
    return json.dumps(argsData)


# index
@app.route('/', methods=['GET', 'POST'])
def index():
    alive = hosts.query.filter_by(status=1).count()
    args = {'cmdCount': cmdCount, 'group': howManyGroups -2, 'run': alive, 'stop': howManyHost - alive}
    return render_template('monitor.html', args=args, items=group_kv_dict, groupList=group_k_list)


# 文件分发
@app.route('/FileDo/', methods=['GET', 'POST'])
def fileDo():
    if request.method == "POST":
        ansible = runner.ansibleRunner(inventoryPath)
        global cmdCount
        cmdCount += 1
        jsonData = request.get_json()
        host = jsonData['host']
        module_name = jsonData['src']
        module_args = jsonData['dest']
        ansible.run(host, 'copy', 'src=' + module_name + ' ' + 'dest=' + module_args)
        # ansible.run('web129', 'copy', 'src=~/test.abc dest=~/abc/')

        # 结果
        result = ansible.get_result()
        data = {}
        data['status'] = 'success'
        data['successHosts'] = list(result['success'].keys())
        data['failedHosts'] = list(result['failed'].keys())
        data['unreachableHosts'] = list(result['unreachable'].keys())
        data['hosts'] = {}
        if result['success']:
            for dict in result['success']:
                data['hosts'][dict] = result['success'][dict]
        if result['failed']:
            for dict in result['failed']:
                data['hosts'][dict] = result['failed'][dict]
        if result['unreachable']:
            for dict in result['unreachable']:
                data['hosts'][dict] = result['unreachable'][dict]
        return json.dumps(data)
    else:
        return render_template('filedo.html', groupList=group_k_list)


@app.route('/Monitor/', methods=['GET', 'POST'])
def monitor():
    alive = hosts.query.filter_by(status=1).count()
    args = {'cmdCount': cmdCount, 'group': howManyGroups-2, 'run': alive, 'stop': howManyHost-alive}
    return render_template('monitor.html', args=args, groupList=group_k_list, items=group_kv_dict)


@app.route('/Playbook/', methods=['GET', 'POST'])
def playbook():
    return render_template('playbook.html')


@app.route('/Shell/', methods=['GET', 'POST'])
def shell():
    return render_template('shell.html')


'''
    命令模式，返回json
    json：
    data[status]:success/failed 返回数据的json状态类型
    data[successHosts]:成功执行或者返回信息的ip列表
    data[failedHosts]：执行失败的主机ip列表
    data[unreachableHosts]：无法到达的主机ip列表
    data[host]：机器的具体状态列表，key中保存stdout_lines
    
'''


@app.route('/Command/', methods=["GET", "POST"])
def commandRun():
    if request.method == "POST":
        global cmdCount
        cmdCount += 1
        jsonData = request.get_json()
        print(jsonData)
        host = jsonData['host']
        module_name = jsonData['module_name']
        module_args = jsonData['module_args']
        ansible = runner.ansibleRunner(inventoryPath)
        ansible.run(host, module_name, module_args)
        # 结果
        result = ansible.get_result()
        print(result)
        data = {}
        data['status'] = 'success'
        data['successHosts'] = list(result['success'].keys())
        data['failedHosts'] = list(result['failed'].keys())
        data['unreachableHosts'] = list(result['unreachable'].keys())
        data['hosts'] = {}
        if result['success']:
            for dict in result['success']:
                data['hosts'][dict] = result['success'][dict]
        if result['failed']:
            for dict in result['failed']:
                data['hosts'][dict] = result['failed'][dict]
        if result['unreachable']:
            for dict in result['unreachable']:
                data['hosts'][dict] = result['unreachable'][dict]
        return json.dumps(data)
    return render_template('command.html', groupList=group_k_list)


# 测试路由
@app.route('/ops/testPing', methods=['GET'])
def testPing():
    # 获取服务器磁盘信息
    # ansible.run('all', 'setup', "filter='ansible_mounts'")
    ansible.run('all', 'command', 'ping 192.168.14.131 -c 5')
    # 结果
    result = ansible.get_result()
    # 成功
    succ = result['success']
    # 失败
    failed = result['failed']
    # 不可到达
    unreachable = result['unreachable']

    print(succ)
    print(failed)
    print(unreachable)

    return "test ok!"


# 进程监控 测试API
# 30s脚本传回json，若服务器无反馈3s持续向服务器发送
@app.route('/processPost/', methods=["GET", "POST"])
def processmonitor():
    if request.method == "POST":
        jsonData = request.get_json()
        print(jsonData)
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        db.session.merge(processMonitor(jsonData['pName'], jsonData['HostName'], jsonData['HostIP'], jsonData["CPU"],
                                        jsonData['Memory'], jsonData['RunTime'], jsonData["StartTime"],
                                        '', now, jsonData['HostIP']+':'+jsonData['pName']))
    db.session.commit()
    return 'ok'


# 文件系统监控 测试API
# 300s监控脚本传回json，无反馈3s间断向服务器持续发送
@app.route('/FSMonitor/', methods=["GET", "POST"])
def fs():
    if request.method == "POST":
        jsonData = request.get_json()
        print(jsonData)
        usage = tool.percent2int(jsonData['Usage'])
        jsonData['Usage'] = usage
        now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        db.session.merge(fileSystemMonitor(jsonData['FilePath'], jsonData['HostIP'], jsonData['HostName'], jsonData['FS'],
                                          jsonData['Volume'], jsonData['Usage'], now, ''))
    db.session.commit()
    return 'ok'


# 心跳链接
@app.route('/pengpeng/', methods=['POST'])
def pengpeng():
    data = request.get_json()
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    host = hosts.query.filter_by(hostIP=data['IP']).first()
    if host is None:
        print(data['IP']+'is unknown!')
    else:
        hosts.query.filter_by(hostIP=data['IP']).update({'timestamp': now})
    db.session.commit()
    return 'ok'


# 内存监控
@app.route('/memory/', methods=['POST'])
def memMonitor():
    data = request.get_json()
    now = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
    model = memoryMonitor(hostIP=data['HostIP'], cache=data['cache'], free=data['free'],
                          share=data['share'], total=data['total'], used=data['used'],
                          available=data['available'], time=now)
    print(model)
    db.session.merge(model)
    db.session.commit()
    return "copy that!"
