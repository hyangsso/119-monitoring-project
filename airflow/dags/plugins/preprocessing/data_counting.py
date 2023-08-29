from plugins.preprocessing.db_connecting import connect_db

# basic info는 존재하나 detail info table에 존재하지 않는 hpids를 계산하는 class
class DataCounter:

    def __init__(self):
        self.cursor = None

    def connect_db(self):
        _, self.cursor = connect_db()

    def get_retry_hpids(self):
        query = '''
            SELECT HOSPITAL_BASIC_INFO.hpid, HOSPITAL_BASIC_INFO.center_type
            FROM HOSPITAL_BASIC_INFO
            LEFT JOIN HOSPITAL_DETAIL_INFO ON HOSPITAL_BASIC_INFO.hpid = HOSPITAL_DETAIL_INFO.hpid
            WHERE HOSPITAL_DETAIL_INFO.hpid IS NULL;
        '''
        self.cursor.execute(query)
        return self.cursor.fetchall()

    def count_data_in_rds(self, **kwargs):
        self.connect_db()
        retry_hpids = self.get_retry_hpids()

        if not len(retry_hpids) == 0:
            kwargs['ti'].xcom_push(key='count_result', value=False)
            kwargs['ti'].xcom_push(key='retry_hpids', value=retry_hpids)