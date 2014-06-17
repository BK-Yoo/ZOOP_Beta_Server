# -*- coding: utf-8 -*-
import datetime
import pytz

import hashlib

from pymongo.errors import OperationFailure, AutoReconnect, DuplicateKeyError

import bson
from bson import json_util
from bson.errors import InvalidId

from ens_app.helper import formatchecker
from ens_app.helper import interpreter

NO_FACEBOOK_EMAIL = 0

def safe_token_get_call(call):
    def _safe_token_get_call(*args, **kwargs):
        try:
            return call(*args, **kwargs)

        except (KeyError, ValueError, TypeError, InvalidId):
            return interpreter.server_status_code['SERVERERROR']

        except StopIteration:
            return interpreter.server_status_code['FORBIDDEN']

        except (OperationFailure, AutoReconnect, DuplicateKeyError):
            return interpreter.server_status_code['SERVERERROR']

    return _safe_token_get_call

class GateKeeper(object):

    def __init__(self, member_collection, request_token_collection):

        #gate keeper는 토큰 관리와 회원 출입 관리를 직접 처리한다
        self.member_col = member_collection
        self.request_token_col = request_token_collection

        #토큰 발급 시에 쓰이는 헤더
        self.token_issue = ('HTTP_X_NALBY_CLIENT', 'NALBY_REQUEST_7832')

        #토큰 반납 시에 쓰이는 헤더
        self.token_return = ('HTTP_X_NALBY_CLIENT', 'NALBY_RETURN_1873')

        #리퀘스트 토큰의 request 헤더 키
        self.request_token_key = 'HTTP_X_NALBY_REQUEST'

        #엑세스 토큰의 request 헤더 키
        self.access_token_key = 'HTTP_X_NALBY_ACCESS'

        #관리자 권한의 요청 헤더
        self.admin_access_key = {'id': ('HTTP_X_NALBY_ADMIN', 'nalby_admin'),
                                 'pw': ('HTTP_X_NALBY_ADMIN_SECRET_KEY', 'nalby3178##@*%$@#!D!DACZ')}

        #엑세스 토큰의 만료기간(일)
        self.access_token_valid_period = 30

        #입력되는 로그인 정보 중 비밀번호 정보의 처리 방식
        self.decrypt_type = dict(NORMAL=0, FACEBOOK=1)

        #엑세스 토큰의 만료기간 확인 등 시간을 비교할 때 쓰이는 기준 time zone
        self.server_time_zone = pytz.utc

        #로그인 하는 회원의 타입
        self.member_type = dict(NORMAL=0, FACEBOOK=1)

    #입력되는 비밀번호 정보를 암호화하여 저장한다
    def encrypt_user_password(self, password):
        return hashlib.sha224(password).hexdigest()

    @safe_token_get_call
    def extract_user_id_from_access_token(self, access_token):
        return access_token['md']['oi']

    def make_request_token(self):
        #request token에서 필요한 정보는 object id 하나 뿐이기 때문에
        #insert의 결과로 request token의 object id가 반환된다.
        return self.request_token_col.insert({'ca': datetime.datetime.utcnow()})

    @safe_token_get_call
    def issue_request_token(self, request):
        if self.token_issue[0] in request.META and request.META[self.token_issue[0]] == self.token_issue[1]:
            return self.make_request_token()

        else:
            return False

#    @safe_token_get_call
#    def pickup_request_token(self, request):

#        if self.token_return[0] in request.META and request.META[self.token_return[0]] == self.token_return[1]:
#            request_token = interpreter.load_json_from_request(request)

#            if request_token:
#                if self.request_token_col.remove(request_token['rt']):
#                    return interpreter.server_status_code['OK']

#                else:
#                    return interpreter.server_status_code['SERVERERROR']

#        return interpreter.server_status_code['BADREQUEST']

    def is_our_member(self, request):

        access_token = self.get_valid_access_token(request)

        if (formatchecker.is_correct_data_format(access_token, formatchecker.data_type['A_TOKEN']) and
                self.member_col.find({'md.at._id': access_token['_id']},
                                     {'_id': 0, 'md.at': 1}
                                     ).limit(1).count(True)):
            return access_token

        return False

    def is_access_token_valid(self, access_token):
        #엑세스 토큰의 파기 날짜를 불러온다.
        expiration_date = access_token['md']['ed']
        #현 시점의 시간을 time zone 정보와 함께 생성
        current_date = datetime.datetime.utcnow().replace(tzinfo=self.server_time_zone)

        #파기 시점이 되었는지 확인한다.
        if current_date < expiration_date:
            return True
        else:
            return False

    @safe_token_get_call
    def is_our_valid_member_request(self, request):

        access_token = self.is_our_member(request)

        if access_token and self.is_access_token_valid(access_token):
            return access_token

        else:
            return False

    def get_valid_access_token(self, request):
        if self.access_token_key in request.META:
            #엑세스토큰의 정보를 bson 형태로 복구한다.
            return json_util.loads(request.META[self.access_token_key])

        else:
            return None

    @safe_token_get_call
    def is_our_service_guest_request(self, request):

        if self.request_token_key in request.META:
            #request token의 정보를 bson 형태로 변환해준다.
            request_token = json_util.loads(request.META[self.request_token_key])

            boolean_answer = request_token and self.request_token_col.find({'_id': request_token},
                                                                           {'_id': 1}
                                                                            ).limit(1).count(True)
            return boolean_answer

        else:
            return False

    #유저가 보낸 인증정보의 암호를 해독한다.
    def decrypt_password(self, auth_info, decrypt_type):
        if decrypt_type == self.decrypt_type['FACEBOOK']:

            #간혹 페이스북 회원 정보에서 email 주소를 가져오지 못하는 경우가 있다
            #이 경우 통신규약에 따라 id에 '0'을 보내게 된다
            if auth_info['id'].isdigit() and int(auth_info['id']) == NO_FACEBOOK_EMAIL:
                #통신 규약에 따라 fi 항목에 유저의 페이스북 교유번호가 역순으로 오게 된다
                #이메일 주소가 없으므로 페이스북 고유번호를 id로 정한다
                auth_info['id'] = auth_info['fi'][::-1]

            #규약 상 fi에 오는 값의 역순 값을 비밀번호로 한다
            auth_info['pw'] = self.encrypt_user_password(auth_info['fi'][::-1])

            #페이스북 회원이라고 하더라도 일반 회원의 문서 스키마를 따르기 때문에 fi 항목을 제거한다
            auth_info.pop('fi')
            auth_info = {'act': auth_info}
            auth_info['md.mt'] = self.member_type['FACEBOOK']

        else:
            #decrypt_type == self.decrypt_type['NORMAL']:
            auth_info['pw'] = self.encrypt_user_password(auth_info['pw'])
            auth_info = {'act': auth_info}
            auth_info['md.mt'] = self.member_type['NORMAL']

        return auth_info

    def authenticate_guest(self, request):
        #비회원이 인증정보(아이디, 비밀번호 등)을 통해 인증받는 경우
        if self.is_our_service_guest_request(request):

            auth_info = interpreter.load_json_from_request(request)

            if (auth_info and 'id' in auth_info and auth_info['id']
                and 'pw' in auth_info and auth_info['pw']):

                decrypt_type = self.decrypt_type['NORMAL']

            elif (auth_info and 'id' in auth_info and auth_info['id']
                  and 'fi' in auth_info and auth_info['fi']):

                decrypt_type = self.decrypt_type['FACEBOOK']

            else:
                return False

            return self.member_col.find(self.decrypt_password(auth_info, decrypt_type),
                                        {'_id': 0, 'md.at': 1}
                                        ).limit(1).next()['md']['at']

        #기존 회원이 access token을 통해 인증하는 경우
        else:
            return self.is_our_member(request)

    @safe_token_get_call
    def member_login_check(self, request):
        #유저의 엑세스 토큰을 불러온다.
        access_token = self.authenticate_guest(request)

        #엑세스 토큰이 제대로 반환되었는지 확인한다
        #잘 반환이 되었다면, 회원임이 증명되고 새로운 엑세스 토큰을 발급한다
        if access_token:
            new_access_token = self.make_access_token(access_token['md']['oi'])
            user_doc = self.member_col.find_and_modify({'_id': access_token['md']['oi']},
                                                       {'$set': {'md.at': new_access_token}})
            nickname = user_doc['info']['un']
            birthday = user_doc['info']['b']['y']
            gender = user_doc['info']['g']

            return new_access_token, nickname, birthday, gender

        else:
            return interpreter.server_status_code['FORBIDDEN']

    #엑세스 토큰을 만든다.
    def make_access_token(self, user_id=None):
        if not user_id:
            user_id = bson.ObjectId()
        access_token = dict()
        expiration_date = datetime.datetime.utcnow() + datetime.timedelta(days=self.access_token_valid_period)
        access_token['md'] = {'oi': user_id, 'ed': expiration_date}
        access_token['_id'] = bson.ObjectId()
        return access_token

    def is_admin(self, request):
        header = request.META
        if self.admin_access_key['id'][0] in header and self.admin_access_key['pw'][0] in header:
            input_id = header[self.admin_access_key['id'][0]]
            input_pw = header[self.admin_access_key['pw'][0]]

            if input_id == self.admin_access_key['id'][1] and input_pw == self.admin_access_key['pw'][1]:
                return True

        return False

    def issue_admin_request_header(self):
        return {key.replace('HTTP_', ''): value for key, value in self.admin_access_key.values()}