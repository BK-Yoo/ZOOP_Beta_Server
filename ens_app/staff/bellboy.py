#-*- coding:utf-8 -*-
from ens_app import briefcase

__author__ = 'bkyoo'

import requests
from bson import json_util

import boto
from boto.ses.exceptions import SESError


#TODO 푸시 보낼 곳 URL 명시
push_server_url = '172.31.24.27/spu/'
push_types = {'like_comment': 'lc',
              'like_post': 'lp',
              'write_comment': 'wc',
              'to_all': 'ta'}

#TODO 신고 받은 이메일을 적어야 한다.
server_email_address = 'yslee@zzalit.com'
server_notification_receiver = ['yslee@zzalit.com', 'dcmber12@gmail.com']


#TODO 트랜스코딩 서버 URL 명시
transcode_server_url = '172.31.29.148/tvu?pi={post_id}'


def send_report_message(report_target_id):
    """
    Amazon Web Service SES 서비스를 이용하여 메일을 보낸다.
    :param report_target_id: AWS Access Key ID.
    :return: 이메일 모내기 성공 여부를 리턴.
    """

    try:
        conn = boto.connect_ses()
        subject, message = briefcase.get_report_message(report_target_id)
        conn.send_email(server_email_address, subject, message, server_notification_receiver)
        return True

    except SESError:
        return False


def send_push_message(content_id, requester_id, push_type, target_type, push_certification):
    """
    푸시 서버에 정보를 보낸다.
    :param content_id:
    :param requester_id:
    :param push_type:
    :param target_type:
    :param push_certification:
    :return:
    """
    push_paper = briefcase.get_push_payload(content_id, requester_id, push_type, target_type)
    try:
        r = requests.post(push_server_url, data=json_util.dumps(push_paper), headers=push_certification, timeout=1)

    except (requests.ConnectionError, Exception):
        return True

    return True if (r.status_code == 200 or r.status_code == 400) else False


def send_transcode_request(post_id):
    """
    transcode 서버에 요청을 보냄.
    :param post_id:
    :return:
    """
    transcode_request_url = transcode_server_url.format(post_id=post_id.__str__())
    try:
        r = requests.get(transcode_request_url, timeout=4)

    except requests.RequestException:
        return True

    return True if r.ok else False