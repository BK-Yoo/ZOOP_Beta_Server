#-*- coding: utf-8 -*-
__author__ = 'bkyoo'

import datetime
from bson import ObjectId

from ens_app.database import mongoquery
from ens_app.helper import hangul
from ens_app.helper import formatchecker


# clerk 모듈에서 어플리케이션에 사용되는 데이터 구조(포스트, 댓글, 사용자 등)을 MongoDB에 저장할 때 호출된다.
# 호출되면 clerk 모듈이 저장하려는 데이터의 구조에 매칭되는 mongodb document를 python dictionary 형태로 반환한다.


report_msg = ('이 카테고리/태그와 어울리지 않는 움짤',
              '누드 혹은 음란물',
              '희롱하거나 공격하는 내용',
              '폭력성 내포',
              '자해하는 내용',
              '스팸 또는 사기',
              '기타')

push_paylaod_key = {'content_id': 'ci', 'requester_id': 'ri',
                    'push_type': 'pt', 'target_type': 'tt'}

no_facebook_id = 0

amazon_s3_address = 'http://s3-ap-northeast-1.amazonaws.com/content.gifzoop/{reversed_post_id}/p/t2/v.mp4'


# 유저가 수집한 것이 없음을 추가 처리 없이 클라이언트에게 알리기 위해,
# upsert를 쓰지 않기 위해서 일부러 각 수집 컬렉션을 비워둔 상태로 만들어둔다.
def get_user_content_document(user_id, user_favorite_list):
    blank_list = list()
    insert_info = {list_name: blank_list for list_name in user_favorite_list.values()}
    insert_info['_id'] = user_id
    return insert_info


#가입 정보를 바탕으로 저장될 회원 도큐먼트를 만든다.
def get_user_document(user_info, password, access_token):
    user_id = user_info['act']['id']

    # 유저가 페이스북으로 가입을 하는 경우, 드물게 email 주소를 받아오지 못할 수 있다
    # 이 경우 페이스북 id를 기본 id로 설정한다
    if not formatchecker.check_email_format(user_id):
        if user_info['md']['mt'] == 1 and user_id and user_id.isdigit() and int(user_id) == no_facebook_id:
            # 통신 규약 상 account 항목의 password에 페이스북 아이디(고유번호)가 있다.
            # 받아온 페이스북 고유번호로 아이디를 대체한다
            user_info['act']['id'] = user_info['act']['pw']

        else:
            return False

    #access_token의 주인 아이디가 곧 새로운 회원의 아이디다
    user_info['_id'] = access_token['md']['oi']

    user_info['md']['ra'] = 0
    user_info['md']['rc'] = 0

    user_info['info']['kw'] = hangul.analyze_hangul_str(user_info['info']['un'])

    user_info['md']['at'] = access_token
    user_info['act']['pw'] = password

    #회원 가입 후에 엑세스 토큰을 넘겨줘야하므로, 리턴 값에 추가한다.
    return user_info


def get_comment_document(post_id, comment_info):
    comment_info['_id'] = ObjectId()

    comment_info['md']['pi'] = post_id
    comment_info['md']['lc'] = 0
    comment_info['md']['ra'] = 0
    comment_info['md']['rc'] = 0

    #object id가 생성되는 시간과
    #ca(생성시간)에 항목이 삽입되는 시간이 다를 수가 있어,
    #object id의 생성시간을 ca로 정한다.
    comment_info['md']['ca'] = comment_info['_id'].generation_time

    return comment_info


def get_tag_document(tag_id, category_id):
    tag_doc = dict(_id=tag_id)
    tag_doc['kw'] = hangul.analyze_hangul_str(tag_id)
    tag_doc['md'] = {'cg': category_id}
    tag_doc['md']['ra'] = 0
    tag_doc['md']['ca'] = datetime.datetime.utcnow()
    tag_doc['md']['sc'] = 0
    tag_doc['md']['fc'] = 0

    return tag_doc


def get_post_document(post_info):
    post_info['_id'] = ObjectId()
    post_info['md']['ca'] = post_info['_id'].generation_time
    post_info['md']['cc'] = 0

    #크롤러가 등록하는 게시물에는 vu가 있지만, 일반 게시자가 올리는 포스트에는 url이 없다
    #데이터의 일관성과 클라이언트와의 원활한 통신을 위해, 비어있는 값을 만든다.
    #2014.04.17 - 아마존 s3에 올리는 방법 말고도, 리소스 트래픽을 줄이기 위해
    #다른 호스팅 업체에 저장된 리소스의 URL로 vu를 채워서 보낼 수 있다
    #2014.05.07 - 외부 URL을 뜻하는 vu의 종류가 늘어날 수 있다
    #2014.05.18 - 'vu'가 하나의 스트링을 갖는 dict이 아니라 URL과 해당 정보를 표현하는 키로 이루어진 dict을 갖는다.

    #[ 'gfycat mp4 url', 'crawling gif url', 'aws s3 mp4 url', 'gfycat gif url', 'gfycat webm url' ]
    video_link = ['', '', '', '', '']
    video_link[2] = amazon_s3_address.format(reversed_post_id=post_info['_id'].__str__()[::-1])

    if 'vu' in post_info['md']:
        video_link[1] = post_info['md']['vu']

    post_info['md']['vu'] = video_link

    if 'sf' not in post_info['md']:
        post_info['md']['sf'] = False

    #업로드 프로그램에 라이크 수가 있을 경우는 그대로 그 숫자를 적용한다
    if 'lc' not in post_info['md']:
        post_info['md']['lc'] = 0
        post_info['md']['ra'] = 0

    return post_info, post_info['_id']


def get_reg_id_document(registration_id):
    return {'_id': registration_id, 'pt': True}


def get_report_message(target_id):
    report_message = ReportMessage()
    return report_message.make_report_email_message(target_id)


def get_push_payload(content_id, requester_id, push_type, target_type):
    return {push_paylaod_key['content_id']: content_id,
            push_paylaod_key['requester_id']: requester_id,
            push_paylaod_key['push_type']: push_type,
            push_paylaod_key['target_type']: target_type}


def get_report_document(reporter_id, report_type, report_text, target_type):
    report = dict()
    #TODO 이메일을 넣어야하는데, db 연결 문제 때문에 추후에 수정하도록 한다.
    report['em'] = reporter_id

    #사용자를 신고하는 경우 게시물 및 댓글 신고 사유와 내용이 같음에도 불구하고
    #사용자의 사유 리스트의 인덱스가 하나 더 적다.
    #따라서 1을 더해주어, 게시물 및 댓글 신고 사유 리스트를 그대로 사용한다.
    if target_type == mongoquery.content_type['USER']:
        report_type += 1

    try:
        report['rt'] = report_msg[report_type]

    except IndexError:
        return False

    if report_type == 6:
        if report_text and 'msg' in report_text:
            report['msg'] = report_text['msg']
        else:
            report['msg'] = ''

    return report


class ReportMessage(object):
    def __init__(self):

        self.report_email_subject = '{target_id}번 게시물 에 대한 다수의 신고가 접수되었습니다.'
        self.report_email_message = '''많은 유저들의 신고가 접수되었습니다.
신고된 컨텐츠: {target_id}
신고 프로그램을 통한 신속한 처리를 부탁드립니다.
'''

    def make_report_email_message(self, target_id):
        subject = self.report_email_subject.format(target_id=target_id)
        message = self.report_email_message.format(target_id=target_id)
        return subject, message