# -*- coding: utf-8 -*-
__author__ = 'bkyoo'

data_type = {'NEW_POST': 0,
             'MOD_POST': 1,
             'NEW_COMMENT': 2,
             'MOD_COMMENT': 3,
             'NEW_MEM': 4,
             'MOD_MEM': 5,
             'A_TOKEN': 6,
             'MESG': 7,
             'POST_FILE': 8,
             'PROFILE_FILE': 9,
             'F_MSG': 10}

ROOT_PATH = 0

#주고 받는 정보들은 모두 JSON 형식이다.
#Json 정보들은 다음과 같은 형태의 정보를 통해 구조 검사가 된다.
#( (키가 있는 경로), 그 경로에 있어야 하는 키)
# 예를 들어 ( ('md', 'au'), 'un') 형태의 검사식이 있다면,
# {'md' :
#       {'au' :
#               {'un': 'value'}
#       }
# }
#위와 같은 구조의 JSON이 맞는지 검사한다.

# 각 데이터 타입에 따른 JSON 검사식은 다음과 같다.
data_format = {data_type['NEW_POST']: [#게시물 내용
                                       (('co',), 'ti'), (('co',), 'tx'), (('co',), 'tl'),
                                       #게시물 부가 정보
                                       (('md', 'au'), 'un'), (('md', 'au'), 'ui'),
                                       (('md',), 'pr'), (('md',), 'cg'),
                                       (('md',), 'wd'), (('md',), 'ht'), (('md',), 'vd')],

               data_type['MOD_POST']: [(('co',), 'ti'), (('co',), 'tx'), (('co',), 'tl'),
                                       (('md',), 'pr'), (('md',), 'cg')],

               data_type['NEW_COMMENT']: [(('md', 'au'), 'un'), (('md', 'au'), 'ui'), (('md',), 'au'),
                                          #댓글 내용 정보
                                          (('co',), 'tx')],

               data_type['MOD_COMMENT']: [(ROOT_PATH, 'tx')],

               data_type['NEW_MEM']: [#사용자 인적 사항
                                      (('info',), 'un'),
                                      (('info', 'b'), 'y'), (('info', 'b'), 'm'), (('info', 'b'), 'd'),
                                      (('info',), 'g'),
                                      #사용자 계정 정보
                                      (('act',), 'id'), (('act',), 'pw'),
                                      #사용자 계정 종류
                                      (('md',), 'mt')],

               data_type['MOD_MEM']: [(ROOT_PATH, 'un'), (ROOT_PATH, 'cpw'), (ROOT_PATH, 'mpw')],

               data_type['A_TOKEN']: [(ROOT_PATH, '_id'),
                                      (('md',), 'oi'), (('md',), 'ed')],

               data_type['MESG']: [(ROOT_PATH, 'msg'), (ROOT_PATH, 'em')],

               data_type['POST_FILE']: [(ROOT_PATH, 'v'), (ROOT_PATH, 'st'), (ROOT_PATH, 'bt')],
               data_type['PROFILE_FILE']: [(ROOT_PATH, 'bp'), (ROOT_PATH, 'sp')],
               data_type['F_MSG']: [(ROOT_PATH, 'gmu')]}



def is_correct_data_format(input_data, input_data_type):
    return all(check_key_in_dict(input_data, check_path, target_key)
               for check_path, target_key in data_format[input_data_type]) if input_data else False


def check_key_in_dict(input_data, check_path, target_key):
    if check_path:
        bring_remain_data_key = check_path[0]
        remain_path = check_path[1:]
        try:
            return check_key_in_dict(input_data[bring_remain_data_key], remain_path, target_key)

        except KeyError:
            return False

    else:
        return target_key in input_data


def check_email_format(input_str):
    return isinstance(input_str, str) and '@' in input_str and '.' in input_str