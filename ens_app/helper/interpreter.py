# -*- coding: utf-8 -*-
from bson import json_util
from bson import ObjectId
from bson.errors import InvalidId
from django.http import HttpResponse
from django.http import HttpResponseForbidden
from django.http import HttpResponseBadRequest
from django.http import HttpResponseNotFound
from django.http import HttpResponseServerError

from ens_app.database.mongoquery import content_type


attach_ft = dict(VIDEO='v', SMALL_THUMBNAIL='st', BIG_THUMBNAIL='bt', BIG_PROFILE='bp', SMALL_PROFILE='sp')
server_status_code = dict(OK=200, BADREQUEST=400, FORBIDDEN=403, NOTFOUND=404, SERVERERROR=0)


parsing_type = dict(ID=1, INTEGER=2, STRING=3)
url_param_type = dict(NICKNAME='un', USER='ui', POST='pi', COUNT='ct', COMMENT='cid',
                      CATEGORY='cg', TAG='tn', REPORTTYPE='rtp', THPOST='thpi', THTAG='thtn', THCOMMENT='thcid',
                      USERID='em', OBJECTID='oid',
                      REGISTRATIONID='ri', PUSH='pu',
                      URL='url')
response_list_type = dict(COMMENTLIST='cl', USERCOLLECTION='cpl', POSTLIST='pl',
                          CATEGORYLIST='cgl', TAGLIST='tl', USERLIST='nl')

post_file_type = {'VIDEO': '/p/t2/v.mp4', 'BIG_THUMBNAIL': '/p/t1/t.jpg', 'SMALL_THUMBNAIL': '/p/t0/t.jpg'}
profile_file_type = {'BIG_PROFILE': '/u/t1/p.jpg', 'SMALL_PROFILE': '/u/t0/p.jpg'}
file_format_type = {'MP4': 'video/mp4', 'JPEG': 'image/jpeg'}

response_content_type = 'application/json'

amazon_s3_url = 'http://s3-ap-northeast-1.amazonaws.com/content.gifzoop/{reversed_post_id}/p/t2/v.mp4'

content_limit = 40

class UrlParameter(object):

    # Request에 실려온 파라미터들을 정해진 타입에 따라 값을 바꿔준다
    # 파라미터의 타입과 키 값은 미리 정해져있다

    def __init__(self, url_param, req_get):
        self.key = url_param
        self.pars_type = self.check_type_of_param()
        self.value = self.convert_parameter(req_get)

    def get_key(self):
        return self.key

    def get_value(self):
        return self.value

    def convert_parameter(self, req_get):
        converted_param = 0

        if self.pars_type and self.key in req_get:
            param_value = req_get[self.key].strip()

            if param_value:
                try:
                    if self.pars_type == parsing_type['ID']:
                        converted_param = ObjectId(param_value)

                    elif self.pars_type == parsing_type['STRING']:
                        converted_param = param_value

                    elif self.pars_type == parsing_type['INTEGER']:
                        converted_param = int(param_value)

                        if self.key == url_param_type['COUNT']:
                            converted_param = self.restrict_number_of_contents(converted_param)

                    else:
                        return converted_param

                except InvalidId:
                        return 0

                except ValueError:
                        return 0

        return converted_param

    def check_type_of_param(self):
        pars_type = None

        if self.key:
            if self.key == url_param_type['USER']:
                #유저 아이
                pars_type = parsing_type['ID']

            elif self.key == url_param_type['POST']:
                #포스트의 아이디
                pars_type = parsing_type['ID']

            elif self.key == url_param_type['TAG']:
                #태그 이름 = 태그 아이디
                pars_type = parsing_type['STRING']

            elif self.key == url_param_type['COMMENT']:
                #댓글의 아이디
                pars_type = parsing_type['ID']

            elif self.key == url_param_type['CATEGORY']:
                #카테고리 이름 = 카테고리 아이디
                pars_type = parsing_type['STRING']

            elif self.key == url_param_type['THPOST']:
                #기준점 포스트 아이디
                pars_type = parsing_type['ID']

            elif self.key == url_param_type['THCOMMENT']:
                #기준점 댓글 아이디
                pars_type = parsing_type['ID']

            elif self.key == url_param_type['THTAG']:
                #기준점 태그 이름(아이디)
                pars_type = parsing_type['STRING']

            elif self.key == url_param_type['NICKNAME']:
                #유저 닉네임
                pars_type = parsing_type['STRING']

            elif self.key == url_param_type['COUNT']:
                #불러올 개수
                pars_type = parsing_type['INTEGER']

            elif self.key == url_param_type['REPORTTYPE']:
                #신고 유형
                pars_type = parsing_type['INTEGER']

            elif self.key == url_param_type['USERID']:
                #유저의 계정 아이디
                pars_type = parsing_type['STRING']

            elif self.key == url_param_type['OBJECTID']:
                #컨텐츠의 고유 아이디
                pars_type = parsing_type['ID']

            elif self.key == url_param_type['REGISTRATIONID']:
                #GCM 등록 아이디
                pars_type = parsing_type['STRING']

            elif self.key == url_param_type['PUSH']:
                #푸시 여부
                pars_type = parsing_type['INTEGER']

            elif self.key == url_param_type['URL']:
                #접속되지 않는 url
                pars_type = parsing_type['STRING']

        return pars_type

    #한 번에 불러오는 게시물의 개수를 제한한다.
    #이 클래스의 self.content_number_restriction에 제한 숫자가 지정되어있다.
    def restrict_number_of_contents(self, count):
        if count > content_limit:
            return content_limit

        elif count <= 0:
            return 0

        else:
            return count


#############################################REQUEST PART############################################
def load_json_from_request(request):
    try:
        return json_util.loads(request.read())

    except ValueError:
        return 0


def extract_file_from_request(request, file_key):
    return request.FILES[file_key]


def extract_parameter_from_request(request, *params):
    req_get = request.GET
    param_dict = {param: UrlParameter(param, req_get).get_value() for param in params}

    if any(param_dict.values()):
        return param_dict

    else:
        return 0


def get_target_content_info(param):

    if url_param_type['COMMENT'] in param and param[url_param_type['COMMENT']]:

        if param[url_param_type['POST']]and url_param_type['POST'] in param:
            return (param[url_param_type['COMMENT']], param[url_param_type['POST']]), content_type['COMMENT']

        else:
            return param[url_param_type['COMMENT']], content_type['COMMENT']

    elif url_param_type['POST'] in param and param[url_param_type['POST']]:
        return param[url_param_type['POST']], content_type['POST']

    elif url_param_type['USER'] in param and param[url_param_type['USER']]:

        if url_param_type['NICKNAME'] in param and param[url_param_type['NICKNAME']]:
            return (param[url_param_type['USER']], param[url_param_type['NICKNAME']]), content_type['USER']

        else:
            return param[url_param_type['USER']], content_type['USER']

    elif url_param_type['TAG'] in param and param[url_param_type['TAG']]:
        return param[url_param_type['TAG']], content_type['TAG']

    elif url_param_type['NICKNAME'] in param and param[url_param_type['NICKNAME']]:
        return param[url_param_type['NICKNAME']], content_type['USER']

    else:
        return 0, 0


def get_attatch_file_info(target_id, target_type):
    root_directory = target_id.__str__()[::-1]

    if target_type == attach_ft['VIDEO']:
        return ''.join([root_directory, post_file_type['VIDEO']]), file_format_type['MP4']

    elif target_type == attach_ft['BIG_THUMBNAIL']:
        return ''.join([root_directory, post_file_type['BIG_THUMBNAIL']]), file_format_type['JPEG']

    elif target_type == attach_ft['SMALL_THUMBNAIL']:
        return ''.join([root_directory, post_file_type['SMALL_THUMBNAIL']]), file_format_type['JPEG']

    elif target_type == attach_ft['BIG_PROFILE']:
        return ''.join([root_directory, profile_file_type['BIG_PROFILE']]), file_format_type['JPEG']

    else:
        return ''.join([root_directory, profile_file_type['SMALL_PROFILE']]), file_format_type['JPEG']


#############################################RESPONSE PART############################################
def json_response(result):

    if result:
        try:
            message, code = (result[0], result[1]) if isinstance(result, tuple) else (None, result)

        except IndexError:
            return HttpResponseServerError(json_util.dumps('servererror'), content_type=response_content_type)

        if code == server_status_code['FORBIDDEN']:
            if not message:
                message = 'forbidden'
            return HttpResponseForbidden(json_util.dumps(message), content_type=response_content_type)

        elif code == server_status_code['BADREQUEST']:
            if not message:
                message = 'badrequest'
            return HttpResponseBadRequest(json_util.dumps(message), content_type=response_content_type)

        elif code == server_status_code['NOTFOUND']:
            if not message:
                message = 'notfound'
            return HttpResponseNotFound(json_util.dumps(message), content_type=response_content_type)

        else:
            #code == server_status_code['OK']:
            if not message:
                message = 'ok'

            response = HttpResponse(json_util.dumps(message), content_type=response_content_type)
            response['Access-Control-Allow-Origin'] = 'http://gifzoop.com, http://yslee.kr'
            return response

    else:
        #server_status_code['SERVERERROR']
        return HttpResponseServerError(json_util.dumps('servererror'), content_type=response_content_type)


def pack_up_request_token(request_token):
    result = ({'rt': request_token}, server_status_code['OK']) if request_token else server_status_code['FORBIDDEN']
    return json_response(result)


def pack_up_login_info(result):
    if isinstance(result, tuple):
        try:
            access_token, user_nickname, user_birthday, user_gender = result

            if access_token:
                result = ({'at': access_token, 'ui': access_token['md']['oi'], 'un': user_nickname,
                           'b': user_birthday, 'g': user_gender},
                          server_status_code['OK'])
                return json_response(result)

            else:
                return json_response(server_status_code['FORBIDDEN'])

        except (KeyError, ValueError):
            return json_response(server_status_code['SERVERERROR'])

    else:
        return json_response(result)


def pack_up_list(result, list_key):
    if isinstance(result, tuple):
        try:
            data_list, status_code = result
        except (KeyError, ValueError):
            return json_response(server_status_code['SERVERERROR'])

        result = {list_key: data_list, 'ct': len(data_list)} if data_list else {list_key: [], 'ct': 0}, status_code

    return json_response(result)


def pack_up_comment(result):
    if isinstance(result, tuple):
        try:
            comment_info = result[0]
            comment_info['md'].pop('ra')
            comment_info['md'].pop('ca')
            comment_info['md'].pop('pi')
            comment_info['md'].pop('rc')
            return json_response((comment_info, server_status_code['OK']))

        except KeyError:
            return json_response(server_status_code['SERVERERROR'])

    else:
        return json_response(result)


def pack_up_amazon_s3_video_url(result):
    if isinstance(result, tuple):
        try:
            post_id, status_code = result

        except (KeyError, ValueError):
            return json_response(server_status_code['SERVERERROR'])

        result = (amazon_s3_url.format(reversed_post_id=post_id.__str__()[::-1]), status_code)

    return json_response(result)