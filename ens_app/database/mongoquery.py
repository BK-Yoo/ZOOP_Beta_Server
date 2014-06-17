# -*- coding: utf-8 -*-

import time

from pymongo.errors import AutoReconnect
from pymongo.errors import OperationFailure
from pymongo.errors import DuplicateKeyError


content_type = dict(COMMENT='c', POST='p', USER='m', TAG='t', PUSH='pu')
EXIST = 1
NOTFOUND = 2
DUPLICATE = 3


#mongo db에서 일어날 수 있는 예상치 못한 에러를 처리하는 데코레이터 함수
# 에러가 발생했을 경우, num_of_tries 만큼 같은 작업을 시도한다.
def safe_mongo_call(call):
    num_of_tries = 3

    #mongodb 작업을 하는 call 메소드를 감는 메소드
    def _safe_mongo_call(*args, **kwargs):
        for num_try in range(num_of_tries):
            try:
                return call(*args, **kwargs)

            except AutoReconnect:
                time.sleep(1)
                continue

            except DuplicateKeyError:
                return DUPLICATE

            except OperationFailure:
                return False

            except Exception:
                continue

        return False

    return _safe_mongo_call

# MongoDB 쿼리를 처리하는 클래스.
class QueryExecuter(object):
    # 생성자에서 db_keeper를 멤버변수로 저장.
    def __init__(self, db_keeper):
        self.db_keeper = db_keeper

#####################################################WRITE OPERATION###################################################
    # target_col 이나 target_type을 넣으면 된다.
    # upsert = true 마지막 인자로 넣으면, 매치 되는 다큐먼트가 없을 경우 새로 만든다. default 값은 False.
    @safe_mongo_call
    def update_content(self, find_query, set_query, target_col, upsert=False):
        target_col = self.db_keeper.connect_to_collection(target_col)
        # upsert (optional): perform an upsert if True
        return target_col.update(find_query, set_query, upsert=upsert)

    @safe_mongo_call
    def insert_data_to_col(self, data, target_col):
        target_col = self.db_keeper.connect_to_collection(target_col)
        return target_col.insert(data)

######################################################READ OPERATION###################################################
    @safe_mongo_call
    def check_existence_of_doc(self, find_query, target_col):
        target_col = self.db_keeper.connect_to_collection(target_col)
        attr_query = {find_query.keys()[0]: 1}

        if target_col.find(find_query, attr_query).limit(1).count(True):
            return EXIST

        else:
            return NOTFOUND

    @safe_mongo_call
    def find_one_doc(self, find_query, attr_query, target_col):
        try:
            target_col = self.db_keeper.connect_to_collection(target_col)

            return target_col.find(find_query, attr_query).limit(1).next()

        except StopIteration:
            return NOTFOUND

    @safe_mongo_call
    def find_target_list_sorted_by(self, find_query, attr_query, sort_query, count, target_col):
        target_col = self.db_keeper.connect_to_collection(target_col)
        return target_col.find(find_query, attr_query).sort(sort_query).limit(count)

    @safe_mongo_call
    def find(self, attr_query, target_col):
        target_col = self.db_keeper.connect_to_collection(target_col)
        return target_col.find({}, attr_query)

#####################################################OTHER OPERATION###################################################
    @safe_mongo_call
    def find_and_modify(self, find_query, set_query, target_col):
        target_col = self.db_keeper.connect_to_collection(target_col)
        target_doc = target_col.find_and_modify(find_query, set_query)
        if target_doc:
            return target_doc

        else:
            return NOTFOUND

    @safe_mongo_call
    def remove_content(self, find_query, target_col):
        target_col = self.db_keeper.connect_to_collection(target_col)
        return target_col.remove(find_query)