# -*- coding: utf-8 -*-
import time
from pymongo.errors import ConnectionFailure
from pymongo import MongoClient

# python dictionary 자료형 db 를 생성. db = {'DB':'nbd', 'LOGDB':'ldb'} 와 같다.
# MongoDB 의 db 이름을 상수로 정의해 놓고, 아래 DBKeeper 클래스에서 pymongo 로 db 를 가져올 때 쓰게 됨.
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

# python dictionary 자료형 collection 을 생성.
# 아래 DBKeeper 클래스에서 MongoDB db 안에 있는 콜렉션을 가져올 때 쓰임.
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

# 아래 DBKeeper 클래스에서 MongoClient 인스턴스를 생성할 때 쓰임. 어느 호스트:포트의 MongoDB와 연결할지 정보를 가지고 있는 리스트.
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
                #MongoDBClient 인스턴스를 생성.
                # tz_aware=boolean (optional)
                # if True, datetime instances returned as values in a document by this MongoClient will be timezone aware (otherwise they will be naive)
                self.m_client = MongoClient(db_seeds, tz_aware=True)
                break

            except ConnectionFailure:
                time.sleep(1)
                continue

        # nbd DB 를 가져옴.
        self.db = self.connect_to_db(db['DB'])
        # member collection(m) 을 가져옴.
        self.member_col = self.connect_to_collection(collection['MEMBER'])
        # request_token collection(rt) 을 가져옴.
        self.req_token_col = self.connect_to_collection(collection['REQUEST_TOKEN'])

    # db 를 가져옴.
    def connect_to_db(self, target_db):
        return self.m_client[target_db]

    # collection 를 가져옴.
    def connect_to_collection(self, target_collection):
        return self.db[target_collection]

# DBKeeper() 인스턴스를 생성.
db_keeper = DBKeeper()

# 생성한 dp_keeper 인스턴스를 반환.
# 외부에서 db_keeper 를 이용하여,
def get_db_keeper():
    return db_keeper
