#-*- coding:utf-8 -*-
__author__ = 'bkyoo'

import requests
from bson import json_util

import boto
from boto.ses.exceptions import SESError

from ens_app.helper import printer


#TODO 푸시 보낼 곳 URL 명시
push_server_url = '172.31.24.27/spu/'
push_types = {'like_comment': 'lc',
              'like_post': 'lp',
              'write_comment': 'wc',
              'to_all': 'ta'}

#TODO 신고 받은 이메일을 적어야 한다.
server_email_address = 'osehyum@gmail.com'
server_notification_receiver = ['immonkey@naver.com']


#TODO 트랜스코딩 서버 URL 명시
transcode_server_url = '172.31.29.148/tvu?pi={post_id}'


def send_report_message(report_target_id):
    try:
        conn = boto.connect_ses()
        subject, message = printer.print_report_message(report_target_id)
        conn.send_email(server_email_address, subject, message, server_notification_receiver)
        return True

    except SESError:
        return False


def send_push_message(content_id, requester_id, push_type, target_type, push_certification):
    #푸시 서버한테 정보를 보낸다
    push_paper = printer.print_push_payload(content_id, requester_id, push_type, target_type)
    try:
        r = requests.post(push_server_url, data=json_util.dumps(push_paper), headers=push_certification, timeout=1)

    except (requests.ConnectionError, Exception):
        return True

    return True if (r.status_code == 200 or r.status_code == 400) else False


def send_transcode_request(post_id):
    transcode_request_url = transcode_server_url.format(post_id=post_id.__str__())
    try:
        r = requests.get(transcode_request_url, timeout=4)

    except requests.RequestException:
        return True

    return True if r.ok else False