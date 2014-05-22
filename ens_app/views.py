# -*- coding: utf-8 -*-
from ens_app.database import mongodb_keeper
from ens_app.helper import formatchecker, interpreter
from ens_app.staff.gate_keeper import GateKeeper
from ens_app.staff.clerk import Clerk
from ens_app.helper.interpreter import json_response, extract_parameter_from_request
from ens_app.helper.interpreter import server_status_code, url_param_type, response_list_type, attach_ft


#db와의 connection 연결은 이곳에서만 이루어진다
#여러개의 client를 쓰는 실수를 하지 않도록 주의한다
mongo_keeper = mongodb_keeper.get_db_keeper()
gate_keeper = GateKeeper(mongo_keeper.member_col, mongo_keeper.req_token_col)
clerk = Clerk(mongo_keeper, gate_keeper)


#amazon web service에서 헬스 체크를 할 때 쓰는 URL
def check_health(request):
    return json_response(server_status_code['OK'])


def admin_access(call):
    def _admin_access(request):
        return call(request) if gate_keeper.is_admin(request) else json_response(server_status_code['FORBIDDEN'])

    return _admin_access


def member_access(call):
    def _member_access(request):
        access_token = gate_keeper.is_our_valid_member_request(request)
        return call(request, access_token) if access_token else json_response(server_status_code['FORBIDDEN'])

    return _member_access


def guest_request(call):
    def _guest_request(request):
        #request token과 access token의 접근을 모두 허용한다.
        if gate_keeper.is_our_service_guest_request(request) or gate_keeper.is_our_valid_member_request(request):
            return call(request)

        else:
            return json_response(server_status_code['FORBIDDEN'])

    return _guest_request


def different_service_by_member_type(call):
    def _different_service_by_user(request):

        #request token을 가지고 접근하는 경우
        if gate_keeper.is_our_service_guest_request(request):
            return call(request)

        #회원이 access token을 가지고 접근하는 경우
        else:
            access_token = gate_keeper.is_our_valid_member_request(request)

            #access 토큰도 request 토큰도 가지고 있지 않으면 접근하지 못한다.
            return call(request, access_token) if access_token else json_response(server_status_code['FORBIDDEN'])

    return _different_service_by_user


def get_request_token(request):
    return interpreter.pack_up_request_token(gate_keeper.issue_request_token(request))


#def return_request_token(request):
#    return json_response(gate_keeper.pickup_request_token(request))


#one find and one insert
@guest_request
def member_sign_up(request):
    raw_user_info = interpreter.load_json_from_request(request)

    if formatchecker.is_correct_data_format(raw_user_info, formatchecker.data_type['NEW_MEM']):
        return interpreter.pack_up_access_token(clerk.sign_up(raw_user_info))

    else:
        return json_response(server_status_code['BADREQUEST'])


#내부적으로 회원 체크하고 있음.
@guest_request
def member_login(request):
    return interpreter.pack_up_access_token(gate_keeper.issue_access_token(request))


@different_service_by_member_type
def register_gcm_reg_id(request, access_token=None):
    param = extract_parameter_from_request(request, url_param_type['REGISTRATIONID'])

    if param:
        registration_id = param[url_param_type['REGISTRATIONID']]
        user_id = gate_keeper.extract_user_id_from_access_token(access_token)

        if registration_id:
            if user_id:
                return json_response(clerk.set_user_gcm_registration_id(registration_id, user_id))

            else:
                return json_response(clerk.save_gcm_registration_id(registration_id))

    return json_response(server_status_code['BADREQUEST'])


@different_service_by_member_type
def modify_push_acceptance(request, access_token=None):
    param = extract_parameter_from_request(request, url_param_type['PUSH'], url_param_type['REGISTRATIONID'])

    if param:
        registration_id = param(url_param_type['REGISTRATIONID'])
        push_acceptance = param(url_param_type['PUSH'])
        user_id = gate_keeper.extract_user_id_from_access_token(access_token)

        if (registration_id and push_acceptance and
                clerk.update_push_acceptance(registration_id, push_acceptance, user_id)):
            return json_response(server_status_code['OK'])

    return json_response(server_status_code['BADREQUEST'])


def check_duplicate_name(request):
    param = extract_parameter_from_request(request, url_param_type['USERID'], url_param_type['NICKNAME'])

    if param:
        return json_response(clerk.check_target_in_database(param))

    else:
        return json_response(server_status_code['BADREQUEST'])


@member_access
def modify_user_info(request, access_token):
    user_id = gate_keeper.extract_user_id_from_access_token(access_token)
    user_info = interpreter.load_json_from_request(request)

    if user_id and user_info and formatchecker.is_correct_data_format(user_info, formatchecker.data_type['MOD_MEM']):
        return json_response(clerk.update_user_data(user_id, user_info))

    else:
        return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_content(request):
    param = extract_parameter_from_request(request, url_param_type['POST'],
                                           url_param_type['COMMENT'], url_param_type['USER'])

    if param:
        target_id, target_type = interpreter.get_target_content_info(param)

        if target_id and target_type:
            return json_response(clerk.get_content(target_id, target_type))

    return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_best_comment(request):
    param = extract_parameter_from_request(request, url_param_type['POST'], url_param_type['COUNT'])

    if param and param[url_param_type['POST']]:
        return interpreter.pack_up_list(clerk.get_best_comment_list(param[url_param_type['POST']],
                                                                    param[url_param_type['COUNT']]),
                                        response_list_type['COMMENTLIST'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_recent_comment(request):
    param = extract_parameter_from_request(request, url_param_type['POST'],
                                           url_param_type['COUNT'], url_param_type['THCOMMENT'])

    if param and param[url_param_type['POST']]:
        return interpreter.pack_up_list(clerk.get_recent_comment_list(param[url_param_type['POST']],
                                                                      param[url_param_type['COUNT']],
                                                                      param[url_param_type['THCOMMENT']]),
                                        response_list_type['COMMENTLIST'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_user_post_collection(request):
    param = extract_parameter_from_request(request, url_param_type['USER'],
                                           url_param_type['COUNT'], url_param_type['THPOST'])

    if param and param[url_param_type['USER']]:
        return interpreter.pack_up_list(clerk.get_user_post_collection(param[url_param_type['USER']],
                                                                       param[url_param_type['COUNT']],
                                                                       param[url_param_type['THPOST']]),
                                        response_list_type['USERCOLLECTION'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@different_service_by_member_type
def get_user_upload_posts(request, access_token=None):
    param = extract_parameter_from_request(request, url_param_type['USER'],
                                           url_param_type['COUNT'], url_param_type['THPOST'])

    if param and param[url_param_type['USER']]:
        request_user_id = gate_keeper.extract_user_id_from_access_token(access_token)

        return interpreter.pack_up_list(clerk.get_user_upload_posts(param[url_param_type['USER']],
                                                                    param[url_param_type['COUNT']],
                                                                    param[url_param_type['THPOST']],
                                                                    request_user_id),
                                        response_list_type['POSTLIST'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@member_access
def get_user_data(request, access_token):
    user_id = gate_keeper.extract_user_id_from_access_token(access_token)

    #찾고자 하는 user_id가 없는 경우에는 요청이 잘못되었다고 클라이언트에게 전달한다
    #user_id가 있는 경우에는 쿼리를 돌려서 결과를 반환한다
    if user_id:
        return json_response(clerk.get_user_data(user_id))

    else:
        return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_category_list(request):
    #카테고리를 불러온 뒤에, 에러가 없다면 결과를 반환한다
    return interpreter.pack_up_list(clerk.get_category_list(), response_list_type['CATEGORYLIST'])


@guest_request
def get_best_of_best_posts(request):
    param = extract_parameter_from_request(request, url_param_type['COUNT'], url_param_type['THPOST'])

    if param:
        #베스트 리스트를 불러오고, 에러가 없다면 결과를 반환한다(error인 경우 result가 false)
        return interpreter.pack_up_list(clerk.get_best_of_best_post_list(param[url_param_type['COUNT']],
                                                                         param[url_param_type['THPOST']]),
                                        response_list_type['POSTLIST'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_best_posts_of_category(request):
    param = extract_parameter_from_request(request, url_param_type['CATEGORY'],
                                           url_param_type['COUNT'], url_param_type['THPOST'])

    if param and param[url_param_type['CATEGORY']]:
        return interpreter.pack_up_list(clerk.get_best_post_list_of_category(param[url_param_type['CATEGORY']],
                                                                             param[url_param_type['COUNT']],
                                                                             param[url_param_type['THPOST']]),
                                        response_list_type['POSTLIST'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_recent_posts_of_category(request):
    param = extract_parameter_from_request(request, url_param_type['CATEGORY'],
                                           url_param_type['COUNT'], url_param_type['THPOST'])

    if param and param[url_param_type['CATEGORY']]:
        return interpreter.pack_up_list(clerk.get_recent_post_list_of_category(param[url_param_type['CATEGORY']],
                                                                               param[url_param_type['COUNT']],
                                                                               param[url_param_type['THPOST']]),
                                        response_list_type['POSTLIST'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_best_tags_of_category(request):
    param = extract_parameter_from_request(request, url_param_type['CATEGORY'], url_param_type['COUNT'])

    if param and param[url_param_type['CATEGORY']]:
        return interpreter.pack_up_list(clerk.get_best_tags_list_of_category(param[url_param_type['CATEGORY']],
                                                                             param[url_param_type['COUNT']]),
                                        response_list_type['TAGLIST'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_best_posts_of_tag(request):
    param = extract_parameter_from_request(request, url_param_type['TAG'],
                                           url_param_type['COUNT'], url_param_type['THPOST'])

    if param and param[url_param_type['TAG']]:
        return interpreter.pack_up_list(clerk.get_best_post_list_of_tag(param[url_param_type['TAG']],
                                                                        param[url_param_type['COUNT']],
                                                                        param[url_param_type['THPOST']]),
                                        response_list_type['POSTLIST'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@guest_request
def get_recent_posts_of_tag(request):
    param = extract_parameter_from_request(request, url_param_type['TAG'],
                                           url_param_type['COUNT'], url_param_type['THPOST'])

    if param and param[url_param_type['TAG']]:
        return interpreter.pack_up_list(clerk.get_recent_post_list_in_tag(param[url_param_type['TAG']],
                                                                          param[url_param_type['COUNT']],
                                                                          param[url_param_type['THPOST']]),
                                        response_list_type['POSTLIST'])

    else:
        return json_response(server_status_code['BADREQUEST'])


@member_access
def write_comment(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['POST'])

    if param:
        post_id = param[url_param_type['POST']]
        comment_info = interpreter.load_json_from_request(request)
        requester_id = gate_keeper.extract_user_id_from_access_token(access_token)

        if (post_id and requester_id and
                formatchecker.is_correct_data_format(comment_info, formatchecker.data_type['NEW_COMMENT'])):

            #댓글 작성 요청자의 id가 request body에 실려있는 댓글 작성자의 id와 일치하는지 확인한다.
            comment_author_id = comment_info['md']['au']['ui']

            if requester_id == comment_author_id:
                return interpreter.pack_up_comment(clerk.insert_comment(post_id, requester_id, comment_info))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def modify_comment(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['COMMENT'])

    if param:
        comment_id = param[url_param_type['COMMENT']]
        comment_info = interpreter.load_json_from_request(request)
        requester_id = gate_keeper.extract_user_id_from_access_token(access_token)

        if (comment_id and requester_id and
                formatchecker.is_correct_data_format(comment_info, formatchecker.data_type['MOD_COMMENT'])):

            return json_response(clerk.update_comment(comment_id, requester_id, comment_info))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def write_post(request, access_token):
    post_info = interpreter.load_json_from_request(request)
    requester_id = gate_keeper.extract_user_id_from_access_token(access_token)

    if requester_id and formatchecker.is_correct_data_format(post_info, formatchecker.data_type['NEW_POST']):

        post_author_id = post_info['md']['au']['ui']

        if post_author_id and requester_id == post_author_id:
            return json_response(clerk.insert_post(post_info))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def modify_post(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['POST'])

    if param:
        post_id = param[url_param_type['POST']]
        new_post_info = interpreter.load_json_from_request(request)
        requester_id = gate_keeper.extract_user_id_from_access_token(access_token)

        if (post_id and requester_id and
                formatchecker.is_correct_data_format(new_post_info, formatchecker.data_type['MOD_POST'])):
            return json_response(clerk.update_post(post_id, requester_id, new_post_info))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def report_contents(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['COMMENT'], url_param_type['POST'],
                                           url_param_type['USER'], url_param_type['REPORTTYPE'])

    if param:
        target_id, target_type = interpreter.get_target_content_info(param)
        report_text = interpreter.load_json_from_request(request)
        reporter_id = gate_keeper.extract_user_id_from_access_token(access_token)
        report_type = param[url_param_type['REPORTTYPE']]

        if target_id and reporter_id and report_type and target_type and 0 <= report_type <= 6:
            return json_response(clerk.report_content(target_id, target_type, reporter_id, report_type, report_text))

    return json_response(result=server_status_code['BADREQUEST'])


@member_access
def delete_contents(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['COMMENT'], url_param_type['POST'],
                                           url_param_type['USER'], url_param_type['TAG'])

    if param:
        user_id = gate_keeper.extract_user_id_from_access_token(access_token)
        target_id, target_type = interpreter.get_target_content_info(param)

        if user_id and target_id and target_type:
            return json_response(clerk.delete_contents(target_id, user_id, target_type))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def like_contents(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['COMMENT'], url_param_type['POST'],
                                           url_param_type['USER'], url_param_type['TAG'])

    if param:
        requester_id = gate_keeper.extract_user_id_from_access_token(access_token)
        target_id, target_type = interpreter.get_target_content_info(param)

        if requester_id and target_id and target_type:
            return json_response(clerk.like_content(target_id, requester_id, target_type))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def cancel_like_contents(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['COMMENT'], url_param_type['POST'],
                                           url_param_type['USER'], url_param_type['TAG'])

    if param:
        user_id = gate_keeper.extract_user_id_from_access_token(access_token)
        target_id, target_type = interpreter.get_target_content_info(param)

        if user_id and target_id and target_type:
            return json_response(clerk.cancel_like_content(target_id, user_id, target_type))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def collect_contents(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['COMMENT'], url_param_type['POST'],
                                           url_param_type['USER'], url_param_type['TAG'], url_param_type['NICKNAME'])

    if param:
        user_id = gate_keeper.extract_user_id_from_access_token(access_token)
        target_id, target_type = interpreter.get_target_content_info(param)

        if user_id and target_id and target_type:
            return json_response(clerk.collect_content(target_id, user_id, target_type))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def cancel_collect_contents(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['COMMENT'],
                                           url_param_type['POST'], url_param_type['USER'], url_param_type['TAG'])

    if param:
        user_id = gate_keeper.extract_user_id_from_access_token(access_token)
        target_id, target_type = interpreter.get_target_content_info(param)

        if user_id and target_id and target_type:
            return json_response(clerk.cancel_collect_content(target_id, user_id, target_type))

    return json_response(server_status_code['BADREQUEST'])


@guest_request
def remove_video_url_broken(request):
    param = extract_parameter_from_request(request, url_param_type['POST'], url_param_type['URL'])

    if param:
        target_id, target_type = interpreter.get_target_content_info(param)
        broken_url = param[url_param_type['URL']]

        if target_id and target_type and broken_url:
            return json_response(clerk.remove_video_url(broken_url, target_id, target_type))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def click_favorite_content(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['COMMENT'], url_param_type['POST'],
                                           url_param_type['USER'], url_param_type['TAG'], url_param_type['NICKNAME'])

    if param:
        user_id = gate_keeper.extract_user_id_from_access_token(access_token)
        target_id, target_type = interpreter.get_target_content_info(param)

        if target_id and user_id and target_type:
            return json_response(clerk.click_favorite_content(target_id, user_id, target_type))

    return json_response(server_status_code['BADREQUEST'])


def auto_complete_contents(request):
    param = extract_parameter_from_request(request, url_param_type['NICKNAME'],
                                           url_param_type['TAG'], url_param_type['COUNT'])

    if param:
        target_id, target_type = interpreter.get_target_content_info(param)

        if target_id and target_type:
            if param[url_param_type['NICKNAME']]:
                list_type = response_list_type['USERLIST']

            else:
                list_type = response_list_type['TAGLIST']

            return interpreter.pack_up_list(clerk.auto_complete_contents(target_id,
                                                                         param[url_param_type['COUNT']],
                                                                         target_type),
                                            list_type)

    return json_response(server_status_code['BADREQUEST'])


@guest_request
def click_content_on_search(request):
    param = extract_parameter_from_request(request, url_param_type['NICKNAME'], url_param_type['TAG'])

    if param:
        target_id, target_type = interpreter.get_target_content_info(param)

        if target_id and target_type:
            return json_response(clerk.click_content(target_id, target_type))

    return json_response(server_status_code['BADREQUEST'])


@member_access
def send_post_video(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['POST'])

    if param:
        target_id, target_type = interpreter.get_target_content_info(param)
        user_id = gate_keeper.extract_user_id_from_access_token(access_token)

        if (target_id and user_id and target_type and
                clerk.check_right_upload(target_id, user_id, target_type) and
                formatchecker.is_correct_data_format(request.FILES, formatchecker.data_type['POST_FILE'])):

            result = clerk.upload_file(target_id,
                                       request.FILES,
                                       clerk.upload_type['post'],
                                       attach_ft['VIDEO'], attach_ft['SMALL_THUMBNAIL'], attach_ft['BIG_THUMBNAIL'])

            if result == server_status_code['OK']:
                return json_response(clerk.complete_upload_post(target_id))

            else:
                return json_response(result)

    return json_response(server_status_code['BADREQUEST'])


@member_access
def send_user_profile_picture(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['USER'])

    if param:
        target_id, target_type = interpreter.get_target_content_info(param)
        user_id = gate_keeper.extract_user_id_from_access_token(access_token)

        if (target_id and user_id and
                clerk.check_right_upload(target_id, user_id, target_type) and
                formatchecker.is_correct_data_format(request.FILES, formatchecker.data_type['PROFILE_FILE'])):

            return json_response(clerk.upload_file(target_id,
                                                   request.FILES,
                                                   clerk.upload_type['user'],
                                                   attach_ft['SMALL_PROFILE'], attach_ft['BIG_PROFILE']))

    return json_response(server_status_code['BADREQUEST'])


@guest_request
def message_to_developer(request):
    message_info = interpreter.load_json_from_request(request)

    if formatchecker.is_correct_data_format(message_info, formatchecker.data_type['MESG']):
        return json_response(clerk.take_message_from_user(message_info))

    else:
        return json_response(server_status_code['BADREQUEST'])


@member_access
def complete_external_upload(request, access_token):
    param = extract_parameter_from_request(request, url_param_type['POST'])

    if param:
        target_id, target_type = interpreter.get_target_content_info(param)

        if target_id and target_type:
            return json_response(clerk.complete_upload_post(target_id))

    return json_response(server_status_code['BADREQUEST'])


@admin_access
def get_flag_report(request):
    param = extract_parameter_from_request(request, url_param_type['OBJECTID'])

    if param and param[url_param_type['OBJECTID']]:
        return json_response(clerk.get_flag_report(param[url_param_type['OBJECTID']]))

    else:
        return json_response(server_status_code['BADREQUEST'])


@admin_access
def delete_any_content(request):
    param = extract_parameter_from_request(request, url_param_type['POST'],
                                           url_param_type['COMMENT'], url_param_type['USER'])

    if param:
        target_id, target_type = interpreter.get_target_content_info(param)

        if target_id and target_type:
            return json_response(clerk.delete_content_by_admin(target_id, target_type))

    return json_response(result=server_status_code['BADREQUEST'])