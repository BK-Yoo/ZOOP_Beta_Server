# -*- coding: utf-8 -*-
import boto
import boto.ses
from boto.s3.key import Key
from boto.exception import S3ResponseError
from pymongo import DESCENDING

from ens_app import briefcase
from ens_app.database.mongoquery import QueryExecuter
from ens_app.database.mongoquery import content_type, DUPLICATE, EXIST, NOTFOUND
from ens_app.database.mongodb_keeper import collection
from ens_app.helper import interpreter
from ens_app.helper.interpreter import url_param_type, server_status_code
from ens_app.helper import hangul
from ens_app.helper import formatchecker
import bellboy




def make_list(cursor, attr=None):
    if cursor:
        if attr:
            return [doc[attr] for doc in cursor], server_status_code['OK']

        else:
            return [doc for doc in cursor], server_status_code['OK']
    else:
        return server_status_code['SERVERERROR']


class Clerk(object):

    # MongoDB로의 쿼리 작업은 모두 이곳에서 처리한다.
    # View 모듈이 요구하는 데이터를 주어진 조건에 맞게 찾아주는 클래스이다.
    # Clerk 클래스로 인해, View 모듈의 함수들은 request의 파라미터들을 정제하는 것과 더불어
    # 적합한 request인지 판단하는 것에 집중할 수 있다

    def __init__(self, db_keeper, gate_keeper):
        self.query_executer = QueryExecuter(db_keeper)
        self.gate_keeper = gate_keeper

        self.popularity_threshold = dict(BEST_COMMENT=3, BEST_POST=7, BEST_TAG=7, BEST_OF_BEST_POST=25)

        # MongoDB에서 쿼리할 때, 필요한 attribute를 정해줄 수 있다
        # 아래의 Dictionary들은 각 데이터 타입에 어떠한 요소들이 필요한지 정의 한다.
        self.target_attr = {'POST': {'_id': 1,
                                     'co.ti': 1, 'co.tx': 1, 'co.tl': 1,
                                     'md.au': 1, 'md.lc': 1, 'md.cc': 1,
                                     'md.vu': 1, 'md.sf': 1,
                                     'md.wd': 1, 'md.ht': 1, 'md.vd': 1,
                                     'md.cg': 1,
                                     'md.pr': 1},
                            'COMMENT': {'_id': 1, 'co.tx': 1, 'md.lc': 1, 'md.au': 1},
                            'TAG': {'_id': 1},
                            'USER': {'_id': 0, 'info.un': 1},
                            'USER_DATA': {'_id': 0, 'cpl': 1, 'lpl': 1, 'lcl': 1, 'ul': 1, 'tl': 1}}

        self.rating_score = dict(LIKE=1, COLLECT=1, SEARCH=0.1)

        self.s3_bucket_name = 'content.gifzoop'

        self.sort_type = dict(HOT=[('md.ra', DESCENDING)],
                              RECENT=[('md.ca', DESCENDING)])

        # 5번 이상 신고가 들어온 게시물은 컨텐츠 관리자에게 통지가 간다
        self.report_threshold = 5

        # 업로드 요청이 실패할 경우, 프로필 사진 업로드(user)이냐 게시물 업로드(post)이냐에 따라
        # 미디어 파일 삭제 처리를 달리해주기 위해 다음과 같은 member 변수를 사용한다.
        self.upload_type = {'user': 0, 'post': 1}

        # 유저가 수집할 수 있는 컨텐츠들을 모아 두는 리스트의 키 값들이다.
        self.user_fv_col = {content_type['POST']: 'cpl',
                            content_type['TAG']: 'tl.tn',
                            content_type['USER']: 'ul.ui'}

        # 좋아요 마크가 표시될 수 있는 콘텐츠들을 모아 두는 리스트이 키 값들이다.
        self.user_like_list = {content_type['POST']: 'lpl',
                               content_type['COMMENT']: 'lcl'}

        # 유저 생성시에 유저가 수집한 컨텐츠 들과 좋아하는 컨텐츠들을 모아 두는 컨테이너를 만들기 위해
        # 아래와 같은 dictionary를 이용한다.
        self.user_favorite_list = dict(COLLECT_POST='cpl', LIKE_POST='lpl', LIKE_COMMENT='lcl',
                                       FAVORITE_USER='ul', FAVORITE_TAG='tl')

        self.current_client_package_name = 'com.nalby.zoop'

###################################################WRITE OPERATION####################################################
    def sign_up(self, raw_user_info):
        password = self.gate_keeper.encrypt_user_password(raw_user_info['act']['pw'])

        access_token = self.gate_keeper.make_access_token()
        user_info = briefcase.get_user_document(raw_user_info, password, access_token)

        if user_info and access_token:

            insert_result = self.query_executer.insert_data_to_col(user_info, collection['MEMBER'])

            if insert_result == DUPLICATE:
                return server_status_code['BADREQUEST']

            elif insert_result:
                content_doc = briefcase.get_user_content_document(user_info['_id'], self.user_favorite_list)

                if self.query_executer.insert_data_to_col(content_doc, collection['FAVORITE_CONTENT']):
                    return access_token, user_info['info']['un'], user_info['info']['b']['y'], user_info['info']['g']

            return server_status_code['SERVERERROR']

        else:
            return server_status_code['BADREQUEST']

    def update_user_data(self, user_id, user_info):
        #닉네임을 바꿀 경우, 다른 데이터는 무시하고 닉네임만을 바꾼다.
        if user_info['un']:
            set_query = {'$set': {'info.un': user_info['un'],
                                  'info.kw': hangul.analyze_hangul_str(user_info['un'])}}

        #비밀번호를 바꿀 경우, 다른 데이터는 무시하고 비밀번호만 바꾼다.
        elif user_info['cpw'] and user_info['mpw']:
            #비밀번호 확인
            find_doc_result = self.query_executer.find_one_doc({'_id': user_id, 'act.pw': user_info['cpw']},
                                                               {'_id': 1},
                                                               collection['MEMBER'])

            if find_doc_result == NOTFOUND:
                return 'wp', server_status_code['OK']

            set_query = {'$set': {'act.pw': user_info['mpw']}}

        else:
            return server_status_code['BADREQUEST']

        update_result = self.query_executer.update_content({'_id': user_id}, set_query, collection['MEMBER'])

        return 'ok', server_status_code['OK'] if update_result else server_status_code['SERVERERROR']

    def set_user_gcm_registration_id(self, registration_id, user_id):
        if self.query_executer.update_content({'_id': user_id},
                                              {'$set': {'ni.ri': registration_id, 'ni.pt': True}},
                                              collection['MEMBER']):

            return server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

    def save_gcm_registration_id(self, registration_id):
        reg_doc = briefcase.get_reg_id_document(registration_id)

        if self.query_executer.insert_data_to_col(reg_doc, collection['PUSH']):
            return server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

    def update_push_acceptance(self, registration_id, acceptance, user_id):
        acceptance = False if acceptance == 'false' else True

        #user가 푸시 허용 여부를 결정할 경우(user_id가 0이 아닌 경우)
        if user_id:
            if self.query_executer.update_content({'ni.ri': registration_id},
                                                  {'$set': {'ni.pt': acceptance}},
                                                  collection['MEMBER']):
                return server_status_code['OK']

        #user가 아닐 경우 모두 push collection의 푸시 허용 여부를 바꿔준다.
        else:
            if self.query_executer.update_content({'_id': registration_id},
                                                  {'$set': {'pt': acceptance}},
                                                  collection['PUSH']):
                return server_status_code['OK']

        return server_status_code['SERVERERROR']

    def insert_comment(self, post_id, requester_id, comment_info):
        comment_doc = briefcase.get_comment_document(post_id, comment_info)

        #댓글이 달린 포스트의 댓글 개수 속성을 1 증가키고, 댓글을 삽입한다.
        result = self.query_executer.insert_data_to_col(comment_doc, collection['COMMENT'])

        if result:
            if result != DUPLICATE:
                self.query_executer.update_content({'_id': post_id}, {'$inc': {'md.cc': 1}}, collection['POST'])
                #클라이언트가 댓글 작성 후에 알아야하는 _id 정보를 보내주기 위해서
                #정해진 통신 규약에 따른 댓글 정보를 반환한다.

                #위 두 정보를 바탕으로 푸시를 보낸다
                #push_certification = self.gate_keeper.issue_admin_request_header()

                #댓글 작성 시에, 게시물 작성자에게 푸시가 가야한다.
                #bellboy.send_push_message(post_id, requester_id,
                #                          bellboy.push_types['write_comment'], interpreter.content_type['POST'],
                #                          push_certification)

                return comment_doc, server_status_code['OK']

            else:
                return server_status_code['BADREQUEST']

        else:
            return server_status_code['SERVERERROR']

    def update_comment(self, comment_id, requester_id, comment_info):
        find_query = {'_id': comment_id, 'md.au.ui': requester_id}
        existence_result = self.query_executer.check_existence_of_doc(find_query, collection['POST'])

        if existence_result == EXIST:
            #타겟 댓글과, 그 댓글의 작성자 id가 일치하는 댓글을 찾는다.
            #그 후 내용을 바꾼다.
            set_query = {'$set': {'co.tx': comment_info['tx']}}

            update_result = self.query_executer.update_content(find_query, set_query, collection['COMMENT'])

            return server_status_code['OK'] if update_result else server_status_code['SERVERERROR']

        elif existence_result == NOTFOUND:
            return server_status_code['FORBIDDEN']

        else:
            return server_status_code['SERVERERROR']

    def insert_post(self, post_info):
        #게시물 정보 dictionary에서 필요한 정보를 추출한다
        tag_list = post_info['co']['tl']
        category_id = post_info['md']['cg']

        if category_id and isinstance(tag_list, list):

            #입력 받은 태그를 DB에 기록하고, 기록된 태그 리스트를 반환한다
            inserted_tag_list = self.get_inserted_tag_list(tag_list, category_id)

            if inserted_tag_list:
                post_doc, post_id = briefcase.get_post_document(post_info)
                post_doc['co']['tl'] = inserted_tag_list

                #동영상과 썸네일이 static server에 올라갈 때까지
                #임시 게시물 콜렉션에 저장해둔다
                if self.query_executer.insert_data_to_col(post_doc, collection['TEMP_POST']):
                    return post_id, server_status_code['OK']

            return server_status_code['SERVERERROR']

        else:
            return server_status_code['BADREQUEST']

    def update_post(self, post_id, requester_id, post_info):
        #포스트 작성자의 요청이 맞는지 확인한다
        find_query = {'_id': post_id, 'md.au.ui': requester_id}
        existence_result = self.query_executer.check_existence_of_doc(find_query, collection['POST'])

        #포스트 작성자의 정보와 일치하는 정보가 있다면 수정을 시작한
        if existence_result == EXIST:
            #포스트에 첨부된 태그들을 콜렉션에 삽입한다.
            tag_list = post_info['co']['tl']
            category_id = post_info['md']['cg']

            if category_id and isinstance(tag_list, list):

                #게시물 수정으로 바뀐 태그를 입력한다
                inserted_tag_list = self.get_inserted_tag_list(tag_list, category_id)

                if inserted_tag_list:
                    #post_info의 'co' 안에 제목, 내용, 태그가 들어있다.
                    post_info['co']['tl'] = inserted_tag_list
                    set_query = {'$set': {'co': post_info['co'],
                                          'md.cg': post_info['md']['cg'],
                                          'md.pr': post_info['md']['pr']}}

                    if self.query_executer.update_content(find_query, set_query, collection['POST']):
                        return server_status_code['OK']

                return server_status_code['SERVERERROR']

            else:
                return server_status_code['BADREQUEST']

        elif existence_result == NOTFOUND:
            return server_status_code['FORBIDDEN']

        else:
            return server_status_code['SERVERERROR']

    def get_inserted_tag_list(self, tags, category_id):
        tag_list = list()

        for tag_id in tags:
            tag_id = tag_id.strip()

            if tag_id:
                tag_doc = briefcase.get_tag_document(tag_id, category_id)

                if self.query_executer.insert_data_to_col(tag_doc, collection['TAG']):
                    tag_list.append(tag_id)

                else:
                    return False

        return tag_list

    def delete_contents(self, target_id, requester_id, target_type):
        if target_type == content_type['COMMENT']:
            #댓글을 지울 경우에는, 포스트에 있는 댓글 수 속성을 하나 줄여야한다.
            #클라이언트에게서 댓글 아이디만 받을 경우 해당 댓글이 속한 게시물의 아이디를 쿼리해야 한다.
            #이 쿼리를 하지 않기 위해 param에 post_id를 따로 받는다.
            #따라서 댓글을 처리할 경우 target_id에 있는 post_id를 따로 처리한다.

            comment_id, post_id = target_id[0], target_id[1]
            existence_result = self.query_executer.check_existence_of_doc({'_id': comment_id, 'md.au.ui': requester_id},
                                                                          target_type)
            if existence_result == EXIST:
                if (self.query_executer.remove_content(comment_id, target_type) and
                        self.query_executer.update_content({'_id': post_id},
                                                           {'$inc': {'md.cc': -1}}, collection['POST'])):
                    return server_status_code['OK']

                else:
                    return server_status_code['SERVERERROR']

        #target_type == content_type['POST']:
        else:
            existence_result = self.query_executer.check_existence_of_doc({'_id': target_id, 'md.au.ui': requester_id},
                                                                          target_type)
            if existence_result == EXIST:
                if self.delete_post_files(target_id) and self.query_executer.remove_content(target_id, target_type):
                    return server_status_code['OK']

                else:
                    return server_status_code['SERVERERROR']

        return server_status_code['FORBIDDEN'] if existence_result == NOTFOUND else server_status_code['SERVERERROR']

    def delete_post_files(self, target_id):
        try:
            s3_conn = boto.connect_s3()
            s3_bucket = s3_conn.get_bucket(self.s3_bucket_name, validate=False)
            s3_key = Key(s3_bucket)

            root_directory = target_id.__str__()[::-1]

            for file_name in interpreter.post_file_type.values():
                s3_key.key = ''.join([root_directory, file_name])
                s3_key.delete()

            return True

        except S3ResponseError:
            return False

    def report_content(self, report_target_id, target_type, reporter_id, report_type, report_text):
        #신고 콜렉션에 신고 정보를 삽입한다.
        report_msg = briefcase.get_report_document(reporter_id, report_type, report_text, target_type)

        if report_msg:
            if self.query_executer.update_content({'_id': report_target_id, 'ct': target_type},
                                                  {'$push': {'rp': report_msg}},
                                                  collection['REPORT'], upsert=True):

                #신고 당한 컨텐츠의 신고 횟수를 증가시킨다.
                find_doc_result = self.query_executer.find_and_modify({'_id': report_target_id},
                                                                      {'$inc': {'md.rc': 1}}, target_type)
                if find_doc_result == NOTFOUND:
                    return server_status_code['BADREQUEST']

                elif find_doc_result:
                    #신고 횟수가 기준을 넘었을 경우.
                    if 'rc' in find_doc_result['md'] and find_doc_result['md']['rc'] >= self.report_threshold:
                        send_result = bellboy.send_report_message(report_target_id)

                        return server_status_code['OK'] if send_result else server_status_code['SERVERERROR']

                    else:
                        return server_status_code['OK']

                else:
                    return server_status_code['SERVERERROR']

        else:
            return server_status_code['BADREQUEST']

    def like_content(self, content_id, requester_id, target_type):
        target_array, target_col = self.user_like_list[target_type], collection['FAVORITE_CONTENT']

        existence_result = self.query_executer.check_existence_of_doc({'_id': requester_id, target_array: content_id},
                                                                      target_col)
        if existence_result == EXIST:
            return server_status_code['BADREQUEST']

        elif existence_result == NOTFOUND:
            if (self.query_executer.update_content({'_id': requester_id},
                                                   {'$push': {target_array: content_id}}, target_col) and
                    self.query_executer.update_content({'_id': content_id},
                                                       {'$inc': {'md.lc': 1, 'md.ra': self.rating_score['LIKE']}},
                                                       target_type)):

                #if target_type == content_type['COMMENT']:
                #    push_type = bellboy.push_types['like_comment']

                #else:
                #    push_type = bellboy.push_types['like_post']

                #위 두 정보를 바탕으로 푸시를 보낸다
                #push_certification = self.gate_keeper.issue_admin_request_header()
                #bellboy.send_push_message(content_id, requester_id, push_type, target_type, push_certification)
                return server_status_code['OK']

            else:
                return server_status_code['SERVERERROR']

        else:
            return server_status_code['SERVERERROR']

    def cancel_like_content(self, target_id, requester_id, target_type):
        target_array, target_col = self.user_like_list[target_type], collection['FAVORITE_CONTENT']

        existence_result = self.query_executer.check_existence_of_doc({'_id': requester_id, target_array: target_id},
                                                                      target_col)
        if existence_result == EXIST:
            if (self.query_executer.update_content({'_id': requester_id},
                                                   {'$pull': {target_array: target_id}}, target_col) and

                    self.query_executer.update_content({'_id': target_id},
                                                       {'$inc': {'md.lc': -1, 'md.ra': -self.rating_score['LIKE']}},
                                                       target_type)):
                return server_status_code['OK']

            else:
                return server_status_code['SERVERERROR']

        elif existence_result == NOTFOUND:
            return server_status_code['BADREQUEST']

        else:
            return server_status_code['SERVERERROR']

    def collect_content(self, target_id, requester_id, target_type):
        #user id를 통해 닉네임을 찾는 쿼리 하나를 줄이기 위해
        #유저를 즐겨찾기하는 경우에는 닉네임이 param에 추가된다
        #추가된 닉네임을 따로 처리해준다.
        if target_type == content_type['USER']:
            target_id, target_nickname = target_id[0], target_id[1]

        target_array, target_col = self.user_fv_col[target_type], collection['FAVORITE_CONTENT']

        existence_result = self.query_executer.check_existence_of_doc({'_id': requester_id, target_array: target_id},
                                                                      target_col)
        if existence_result == EXIST:
            return server_status_code['BADREQUEST']

        elif existence_result == NOTFOUND:
            if target_type == content_type['POST']:
                set_query = {'$push': {'cpl': target_id}}

            elif target_type == content_type['TAG']:
                set_query = {'$push': {'tl': {'tn': target_id,
                                              'sc': 0}}}
            else:
                #target_type == content_type['USER']:
                set_query = {'$push': {'ul': {'ui': target_id, 'un': target_nickname, 'sc': 0}}}

            if (self.query_executer.update_content({'_id': requester_id}, set_query, target_col) and
                    self.query_executer.update_content({'_id': target_id},
                                                       {'$inc': {'md.ra': self.rating_score['COLLECT'], 'md.fc': 1}},
                                                       target_type)):
                return server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

    def cancel_collect_content(self, target_id, request_id, target_type):
        target_array, target_col = self.user_fv_col[target_type], collection['FAVORITE_CONTENT']

        existence_result = self.query_executer.check_existence_of_doc({'_id': request_id, target_array: target_id},
                                                                      target_col)
        if existence_result == EXIST:
            if target_type == content_type['POST']:
                set_query = {'$pull': {'cpl': target_id}}

            elif target_type == content_type['TAG']:
                set_query = {'$pull': {'tl': {'tn': target_id}}}

            else:
                #target_type == content_type['USER']
                set_query = {'$pull': {'ul': {'ui': target_id}}}

            if (self.query_executer.update_content({'_id': request_id}, set_query, target_col) and
                    self.query_executer.update_content({'_id': target_id},
                                                       {'$inc': {'md.ra': -self.rating_score['COLLECT'], 'md.fc': -1}},
                                                       target_type)):
                return server_status_code['OK']

            else:
                return server_status_code['SERVERERROR']

        elif existence_result == NOTFOUND:
            return server_status_code['BADREQUEST']

        else:
            return server_status_code['SERVERERROR']

    def remove_video_url(self, broken_url, target_id, target_type):
        find_query = {'_id': target_id}
        target_doc = self.query_executer.find_one_doc(find_query, {'md.vu': 1}, target_type)

        if not target_doc:
            return server_status_code['SERVERERROR']

        url_list = target_doc['md']['vu']

        for index, url in enumerate(url_list):
            if broken_url == url:
                url_list[index] = ''
                break

        if self.query_executer.update_content({'_id': target_id}, {'$set': {'md.vu': url_list}}, target_type):
            return server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

    def click_favorite_content(self, target_id, user_id, target_type):
        target_array, target_col = self.user_fv_col[target_type], collection['FAVORITE_CONTENT']

        if target_type == content_type['TAG']:
            set_query = {'$inc': {'tl.$.sc': 1}}

        else:
            #target_type == content_type['USER']:
            set_query = {'$inc': {'ul.$.sc': 1}}

        if self.query_executer.update_content({'_id': user_id, target_array: target_id}, set_query, target_col):
            return server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

    def take_message_from_user(self, message_info):
        if self.query_executer.insert_data_to_col(message_info, collection['MESSAGE']):
            return server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

###################################################READ OPERATION####################################################
    def check_target_in_database(self, target_dict):
        if url_param_type['USERID'] in target_dict and target_dict[url_param_type['USERID']]:
            user_id = target_dict[url_param_type['USERID']]

            #이메일 형태 체크
            if formatchecker.check_email_format(user_id):
                find_query = {'act.id': user_id}

            else:
                return server_status_code['BADREQUEST']

        elif url_param_type['NICKNAME'] in target_dict and target_dict[url_param_type['NICKNAME']]:
            find_query = {'info.un': target_dict[url_param_type['NICKNAME']]}

        else:
            return server_status_code['BADREQUEST']

        existence_result = self.query_executer.check_existence_of_doc(find_query, collection['MEMBER'])

        if existence_result:
            message = 'dp' if existence_result == EXIST else 'ok'
            return message, server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

    def get_content(self, target_id, target_type):
        if target_type == content_type['POST']:
            attr_query = self.target_attr['POST']

        elif target_type == content_type['COMMENT']:
            attr_query = self.target_attr['COMMENT']

        else:
            attr_query = self.target_attr['USER']

        find_doc_result = self.query_executer.find_one_doc({'_id': target_id}, attr_query, target_type)

        return (find_doc_result, server_status_code['OK']) if find_doc_result else server_status_code['NOTFOUND']

    def get_user_post_collection(self, requester_id, count, post_id):
        try:
            find_list_result = self.query_executer.find_one_doc({'_id': requester_id}, {'_id':  0, 'cpl': 1},
                                                                collection['FAVORITE_CONTENT'])
            if find_list_result == NOTFOUND:
                return server_status_code['BADREQUEST']

            elif find_list_result and 'cpl' in find_list_result:
                collection_list = find_list_result['cpl']

                start_index = -1

                if post_id:
                    #어디서부터 불러올 것인지, 기준점에 해당하는 포스트의 인덱스를 검색한다.
                    #해당 인덱스까지 포함해서 배열이 반환되므로, 1을 빼준다.
                    start_index = collection_list.index(post_id) - 1

                    if start_index == -1:
                        #해당 인덱스가 마지막 요소일 경우에는 0을 리턴한다.
                        return server_status_code['NOTFOUND']

                #end_index 자체는 불러오기 대상에서 제외되기 때문에, 1을 더 빼준다.
                end_index = start_index - count

                return collection_list[start_index:end_index:-1], server_status_code['OK']

            else:
                return server_status_code['SERVERERROR']

        except (IndexError, ValueError):
            return server_status_code['SERVERERROR']

    def get_user_upload_posts(self, requester_id, count, post_id, request_user_id=None):
        find_query = {'md.au.ui': requester_id}

        if post_id:
            threshold_date = post_id.generation_time
            find_query['md.ca'] = {'$lt': threshold_date}

        if not request_user_id or requester_id != request_user_id:
            #public - read 의 값이 True인, 공개된 포스트만 가져온다.
            find_query['md.pr'] = True

        cursor = self.query_executer.find_target_list_sorted_by(find_query,
                                                                self.target_attr['POST'],
                                                                self.sort_type['RECENT'],
                                                                count,
                                                                collection['POST'])
        return make_list(cursor)

    def get_user_data(self, user_id):
        user_data_list = self.query_executer.find_one_doc({'_id': user_id}, self.target_attr['USER_DATA'],
                                                          collection['FAVORITE_CONTENT'])
        if user_data_list == NOTFOUND:
            return server_status_code['BADREQUEST']

        elif user_data_list:
            if all((list_name in user_data_list) for list_name in self.user_like_list.values()):
                return user_data_list, server_status_code['OK']
            else:
                return server_status_code['SERVERERROR']

        else:
            return server_status_code['SERVERERROR']

    def get_category_list(self):
        attr_key = '_id'
        cursor = self.query_executer.find({attr_key: 1}, collection['CATEGORY'])

        return make_list(cursor, attr_key)

    def get_best_comment_list(self, post_id, count):
        find_query = {'md.pi': post_id,
                      'md.ra': {'$gte': self.popularity_threshold['BEST_COMMENT']}}
        attr_query = self.target_attr['COMMENT']
        sort_query = self.sort_type['HOT']

        cursor = self.query_executer.find_target_list_sorted_by(find_query, attr_query, sort_query, count,
                                                                collection['COMMENT'])
        return make_list(cursor)

        #-기준점이 삭제되어서, 아무 정보도 받아오지 못했을 경우-
        #이 문제를 해결하기 위해서는, 삭제하지 않고 '삭제 처리'만 하거나,
        #기준점을 해당 대상이 아니라 해당 대상에 적용되는 정렬 값(게시물 점수 혹은 생성 시간 등)을 받는 방법 밖에 없다.
        #일단은 삭제처리를 하고, skip을 이용할 수 있는 방법을 고려해야겠다.
        #의견 정리(2014.04.16)
        #값으로 포스트들을 불러온다 하더라도, (MongoDB 기본 정렬) 동점자의 정렬을 랜덤으로 하기 때문에,
        #MongoDB에서 기준점을 기준으로 게시물을 불러오는 방법은 각 기준점이 고유해야 한다는 가정이 있어야한다
        #결국 페이지 넘버로 하거나, 고유한 숫자를 만들어야한다

    def get_recent_comment_list(self, post_id, count, comment_id):
        find_query = {'md.pi': post_id}
        attr_query = self.target_attr['COMMENT']
        sort_query = self.sort_type['RECENT']

        if comment_id:
            threshold_date = comment_id.generation_time
            find_query['md.ca'] = {'$lt': threshold_date}

        cursor = self.query_executer.find_target_list_sorted_by(find_query, attr_query, sort_query, count,
                                                                collection['COMMENT'])
        return make_list(cursor)

    def get_best_of_best_post_list(self, count, post_id):
        find_query = {'md.ra': {'$gte': self.popularity_threshold['BEST_OF_BEST_POST']},
                      'md.pr': True}
        attr_query = self.target_attr['POST']
        sort_query = self.sort_type['RECENT']

        if post_id:
            threshold_date = post_id.generation_time
            find_query['md.ca'] = {'$lt': threshold_date}

        cursor = self.query_executer.find_target_list_sorted_by(find_query, attr_query, sort_query, count,
                                                                collection['POST'])
        return make_list(cursor)

    def get_best_post_list_of_category(self, category_id, count, post_id):
        find_query = {'md.ra': {'$gte': self.popularity_threshold['BEST_POST']},
                      'md.cg': category_id,
                      'md.pr': True}
        attr_query = self.target_attr['POST']
        sort_query = self.sort_type['RECENT']

        if post_id:
            threshold_date = post_id.generation_time
            find_query['md.ca'] = {'$lt': threshold_date}

        cursor = self.query_executer.find_target_list_sorted_by(find_query, attr_query, sort_query, count,
                                                                collection['POST'])
        return make_list(cursor)

    def get_recent_post_list_of_category(self, category_id, count, post_id):
        find_query = {'md.cg': category_id,
                      'md.pr': True}
        attr_query = self.target_attr['POST']
        sort_query = self.sort_type['RECENT']

        if post_id:
            threshold_date = post_id.generation_time
            find_query['md.ca'] = {'$lt': threshold_date}

        cursor = self.query_executer.find_target_list_sorted_by(find_query, attr_query, sort_query, count,
                                                                collection['POST'])
        return make_list(cursor)

    def get_best_tags_list_of_category(self, category_id, count):
        find_query = {'md.cg': category_id,
                      'md.ra': {'$gte': self.popularity_threshold['BEST_TAG']}}
        attr_query = self.target_attr['TAG']
        sort_query = self.sort_type['HOT']

        cursor = self.query_executer.find_target_list_sorted_by(find_query, attr_query, sort_query, count,
                                                                collection['TAG'])
        return make_list(cursor, '_id')

    def get_best_post_list_of_tag(self, tag_id, count, post_id):
        find_query = {'co.tl': tag_id,
                      'md.ra': {'$gte': self.popularity_threshold['BEST_POST']},
                      'md.pr': True}
        attr_query = self.target_attr['POST']
        sort_query = self.sort_type['RECENT']

        if post_id:
            threshold_date = post_id.generation_time
            find_query['md.ca'] = {'$lt': threshold_date}

        cursor = self.query_executer.find_target_list_sorted_by(find_query, attr_query, sort_query, count,
                                                                collection['POST'])
        return make_list(cursor)

    def get_recent_post_list_in_tag(self, tag_id, count, post_id):
        find_query = {'co.tl': tag_id,
                      'md.pr': True}
        attr_query = self.target_attr['POST']
        sort_query = self.sort_type['RECENT']

        if post_id:
            threshold_date = post_id.generation_time
            find_query['md.ca'] = {'$lt': threshold_date}

        cursor = self.query_executer.find_target_list_sorted_by(find_query, attr_query, sort_query, count,
                                                                collection['POST'])
        return make_list(cursor)

    def click_content(self, target_id, target_type):
        find_query = {'info.un': target_id} if target_type == content_type['USER'] else {'_id': target_id}
        set_query = {'$inc': {'md.sc': 1,
                              'md.ra': self.rating_score['SEARCH']}}

        process_result = self.query_executer.find_and_modify(find_query, set_query, target_type)

        if process_result:
            if process_result == NOTFOUND:
                return server_status_code['NOTFOUND']

            else:
                if target_type == content_type['USER']:
                    return process_result['_id'], server_status_code['OK']

                else:
                    return server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

    def auto_complete_contents(self, target_id, count, target_type):
        if target_type == content_type['USER']:
            if target_id == "''":
                find_query = {}

            else:
                target_id = hangul.analyze_hangul_str(target_id)
                find_query = {'info.kw': {'$regex': ''.join(['^', target_id])}}

            cursor = self.query_executer.find_target_list_sorted_by(find_query, {'_id': 1, 'info.un': 1},
                                                                    self.sort_type['HOT'], count, collection['MEMBER'])
            try:
                result_list = [{'un': element['info']['un'], 'ui': element['_id']} for element in cursor]
                return result_list, server_status_code['OK']

            except TypeError:
                return server_status_code['SERVERERROR']

        else:
            #TAG LIST
            if target_id == "''":
                find_query = {}
            else:
                target_id = hangul.analyze_hangul_str(target_id)
                find_query = {'kw': {'$regex': ''.join(['^', target_id])}}

            cursor = self.query_executer.find_target_list_sorted_by(find_query, {'_id': 1}, self.sort_type['HOT'],
                                                                    count, collection['TAG'])
            return make_list(cursor, '_id')

    def check_right_upload(self, target_id, uploader_id, target_type):
        if target_type == content_type['POST']:
            find_query = {'_id': target_id, 'md.au.ui': uploader_id}
            existence_result = self.query_executer.check_existence_of_doc(find_query, collection['TEMP_POST'])
            return True if existence_result == EXIST else False

        else:
            return True if target_id == uploader_id else False

    def complete_upload_post(self, target_id):
        # 실제 파일 업로드가 성공하면 임시 포스트 콜렉션에 있는 포스트 문서를
        # 포스트 콜렉션으로 옮긴다.

        find_doc_result = self.query_executer.find_one_doc({'_id': target_id}, None, collection['TEMP_POST'])
        insert_result = find_doc_result and self.query_executer.insert_data_to_col(find_doc_result, collection['POST'])

        if insert_result == DUPLICATE:
            return server_status_code['BADREQUEST']

        elif insert_result and self.query_executer.remove_content(target_id, collection['TEMP_POST']):
            #bellboy.send_transcode_request(target_id)
            return target_id, server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

    def upload_file(self, target_id, upload_files, upload_type, *params):
        file_name_list = list()
        s3_conn = boto.connect_s3()
        s3_bucket = s3_conn.get_bucket(self.s3_bucket_name, validate=False)
        s3_key = Key(s3_bucket)

        try:
            for param in params:
                filename, file_content_type = interpreter.get_attatch_file_info(target_id, param)
                file_name_list.append(filename)
                s3_key.key = filename
                s3_key.set_contents_from_file(upload_files[param], headers={'Content-Type': file_content_type},
                                              replace=True, policy='public-read')
            return server_status_code['OK']

        except (S3ResponseError, Exception):
            for file_name in file_name_list:
                s3_key.key = file_name
                s3_key.delete()

            if upload_type == self.upload_type['post']:
                self.query_executer.remove_content(target_id, collection['TEMP_POST'])

            return server_status_code['SERVERERROR']

    def get_flag_report(self, target_id):
        find_query = {'_id': target_id}
        attr_query = {'_id': 0, 'rp': 1, 'ct': 1}
        report_doc = self.query_executer.find_one_doc(find_query, attr_query, collection['REPORT'])

        if report_doc and 'rp' in report_doc and 'ct' in report_doc:

            if report_doc['ct'] == content_type['POST'] or report_doc['ct'] == content_type['COMMENT']:
                attr_query = {'_id': 0, 'md.au.ui': 1}
                result_doc = self.query_executer.find_one_doc(find_query, attr_query, report_doc['ct'])

                if result_doc and 'md' in result_doc and 'au' in result_doc['md'] and 'ui' in result_doc['md']['au']:
                    bad_guy_object_id = result_doc['md']['au']['ui']
                    find_query = {'_id': bad_guy_object_id}

            attr_query = {'_id': 0, 'act.id': 1}
            result_doc = self.query_executer.find_one_doc(find_query, attr_query, content_type['USER'])

            if result_doc and 'act' in result_doc and 'id' in result_doc['act']:
                bad_guy_id = result_doc['act']['id'].__str__()
                report_doc['bgi'] = bad_guy_id

            return report_doc, server_status_code['OK']

        else:
            return server_status_code['BADREQUEST']

    def delete_content_by_admin(self, target_id, target_type):
        if target_type == content_type['POST']:
            try:
                s3_conn = boto.connect_s3()
                s3_bucket = s3_conn.get_bucket(self.s3_bucket_name, validate=False)
                s3_key = Key(s3_bucket)

                root_directory = target_id.__str__()[::-1]

                for file_name in interpreter.post_file_type.values():
                    s3_key.key = ''.join([root_directory, file_name])
                    s3_key.delete()

            except S3ResponseError:
                return server_status_code['BADREQUEST']

        else:
            #target_type == content_type['COMMENT']:
            find_query = {'_id': target_id}
            attr_query = {'_id': 0, 'md.pi': 1}

            result_doc = self.query_executer.find_one_doc(find_query, attr_query, target_type)

            if result_doc and 'md' in result_doc and 'pi' in result_doc['md']:
                target_post = result_doc['md']['pi']

                find_query = {'_id': target_post}
                set_query = {'$inc': {'md.cc': -1}}

                self.query_executer.update_content(find_query, set_query, collection['POST'])

        if self.query_executer.remove_content(target_id, target_type):
            return server_status_code['OK']

        else:
            return server_status_code['SERVERERROR']

    def make_initial_message(self, package_name):
        if self.current_client_package_name == package_name:
            is_necessary_to_download_from_new_url = False
            external_download_url = ''
            message_for_users = ''
        else:
            is_necessary_to_download_from_new_url = True
            external_download_url = 'http://googleplay~~~'
            message_for_users = 'zoop이 새로운 어플리케이션으로 재 등장하였습니다!!'

        return {'ind': is_necessary_to_download_from_new_url, 'edu': external_download_url, 'msg': message_for_users}

    def send_app_first_message(self, package_name):
        message = self.make_initial_message(package_name)
        return message, server_status_code['OK']

    def save_gfycat_url_at_post(self, target_id, target_type, requester_id, gfycat_mp4_url):
        result = self.query_executer.find_one_doc({'_id': target_id, 'md.au.ui': requester_id},
                                                  {'_id': 1, 'md.vu': 1},
                                                  target_type)
        if result:
            if result == NOTFOUND:
                return server_status_code['BADREQUEST']

            else:
                url_list = result['md']['vu']
                url_list[0] = gfycat_mp4_url

                if self.query_executer.update_content({'_id': target_id}, {'$set': {'md.vu': url_list}}, target_type):
                    return server_status_code['OK']

        return server_status_code['SERVERERROR']