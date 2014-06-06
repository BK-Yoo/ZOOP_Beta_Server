# -*- coding: utf-8 -*-
import time
from pymongo.errors import ConnectionFailure
from pymongo import MongoClient

db = dict(DB='nbd', LOGDB='ldb')

#Member           - 회원 콜렉션
#Post             - 게시물 콜렉션
#Comment          - 댓글 콜렉션
#Category         - 카테고리 리스트
#Tag              - 태그 콜렉션
#Report           - 게시물/유저 신고 콜렉션
#Request Token    - 요청 토큰 콜렉션
#Favorite Content - 좋아요한 게시물, 수집한 게시물, 즐겨 찾기한 유저 정보가 들어있는 콜렉션
#Message          - 고객의 소리 콜렉션
#Temp Post        - 파일 업로드가 되기 전에, 게시물 정보를 임시저장하는 콜렉션
#Push             - 푸시 허용 여부와, GCM 등록 아이디를 저장하는 콜렉션

collection = dict(MEMBER='m',
                  POST='p',
                  COMMENT='c',
                  CATEGORY='cg',
                  TAG='t',
                  REPORT='r',
                  REQUEST_TOKEN='rt',
                  FAVORITE_CONTENT='fc',
                  MESSAGE='msg',
                  TEMP_POST='tp',
                  PUSH='pu')

# 시드로 레플리카 셋을 넣어야 단일 실패점이 없어진다.
# 시드로 하나의 서버만을 설정해놓을 경우, 그 서버가 죽으면 레플리카 셋에 연결할 수 없다.
#TODO 실제 서버 IP를 레플리카 셋 시드로 넣어야한다
#db_seeds = ['10.0.3.43:27017', '10.0.4.38:27017', '10.0.4.127:27018']

#테스트용 db서버 시드 주소(localhost)
db_seeds = '127.0.0.1:27017'


class DBKeeper(object):
    def __init__(self):
        for index in range(10):
            try:
                self.m_client = MongoClient(db_seeds, tz_aware=True)
                break

            except ConnectionFailure:
                time.sleep(1)
                continue

        self.db = self.connect_to_db(db['DB'])
        self.member_col = self.connect_to_collection(collection['MEMBER'])
        self.req_token_col = self.connect_to_collection(collection['REQUEST_TOKEN'])

    def connect_to_db(self, target_db):
        return self.m_client[target_db]

    def connect_to_collection(self, target_collection):
        return self.db[target_collection]


db_keeper = DBKeeper()


def get_db_keeper():
    return db_keeper