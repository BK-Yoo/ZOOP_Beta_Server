from django.conf.urls import patterns

urlpatterns = patterns('',
                       (r'^check/','ens_app.views.check_health'),
                       (r'^grt/',  'ens_app.views.get_request_token'),
                       (r'^msu/',  'ens_app.views.member_sign_up'),
                       (r'^ml/',   'ens_app.views.member_login'),

                       (r'^rri$',   'ens_app.views.register_gcm_reg_id'),
                       (r'^mpa$',   'ens_app.views.modify_push_acceptance'),

                       (r'^cdn$',  'ens_app.views.check_duplicate_name'),

                       (r'^mui/',  'ens_app.views.modify_user_info'),

                       (r'^gc$', 'ens_app.views.get_content'),

                       (r'^gbc$',  'ens_app.views.get_best_comment'),
                       (r'^grc$',  'ens_app.views.get_recent_comment'),

                       (r'^gupc$', 'ens_app.views.get_user_post_collection'),
                       (r'^guup$', 'ens_app.views.get_user_upload_posts'),

                       (r'^gud/',  'ens_app.views.get_user_data'),

                       (r'^gcl/',  'ens_app.views.get_category_list'),

                       (r'^gbbp$', 'ens_app.views.get_best_of_best_posts'),

                       (r'^gbpc$', 'ens_app.views.get_best_posts_of_category'),
                       (r'^grpc$', 'ens_app.views.get_recent_posts_of_category'),
                       (r'^gbtc$', 'ens_app.views.get_best_tags_of_category'),

                       (r'^gbpt$', 'ens_app.views.get_best_posts_of_tag'),
                       (r'^grpt$', 'ens_app.views.get_recent_posts_of_tag'),

                       (r'^wc$',   'ens_app.views.write_comment'),
                       (r'^mc$',   'ens_app.views.modify_comment'),

                       (r'^dc$',   'ens_app.views.delete_contents'),
                       (r'^rc$',   'ens_app.views.report_contents'),

                       (r'^lc$',   'ens_app.views.like_contents'),
                       (r'^clc$',  'ens_app.views.cancel_like_contents'),

                       (r'^wp/',   'ens_app.views.write_post'),
                       (r'^mp$',   'ens_app.views.modify_post'),
                       (r'^spv$',  'ens_app.views.send_post_video'),
                       (r'^sup$',  'ens_app.views.send_user_profile_picture'),

                       (r'^cc$',   'ens_app.views.collect_contents'),
                       (r'^ccc$',  'ens_app.views.cancel_collect_contents'),

                       (r'^evub$', 'ens_app.views.remove_video_url_broken'),

                       (r'^acc$',  'ens_app.views.auto_complete_contents'),
                       (r'^cfc$',  'ens_app.views.click_favorite_content'),
                       (r'^ccs$',  'ens_app.views.click_content_on_search'),

                       (r'^td/',  'ens_app.views.message_to_developer'),

                       (r'^ceu$',  'ens_app.views.complete_external_upload'),

                       (r'^gfr$',  'ens_app.views.get_flag_report'),
                       (r'^dac$',  'ens_app.views.delete_any_content'),
                       )