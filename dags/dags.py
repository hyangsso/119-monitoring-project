from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
from dotenv import load_dotenv
import os
import json
import xmltodict
import pymysql
import requests

# DAG 설정
default_args = {
    'start_date': datetime(2023, 8, 9),
    'retries': 1,
    'timezone': 'Asia/Seoul',
    'retry_delay': timedelta(minutes=5)
}

dag = DAG(
    'emergency_room_info',
    default_args=default_args,
    schedule_interval=timedelta(days=1),
)

# API 호출
def call_api(url, params, **kwargs):
    url = 'http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire'
    params = {'serviceKey': 'i2nQ5zrOUo6vBQs0nD+h14vmsQMPQuEvfvf+P5BfVQSgkWFMKabetmAYmLLk79BRx7eizGH3707qbtns1K7Z2g==', 'pageNo' : '1', 'numOfRows' : '9999' }

    response = requests.get(url, params=params)
    xmlString = response.text
    jsonString = xmltodict.parse(xmlString)
    
    data = jsonString['response']['body']['items']['item']
    kwargs['ti'].xcom_push(key='list_info_data', value=data)
    return data

# 데이터 적재
def load_data_to_rds(**kwargs):
    data = kwargs['ti'].xcom_pull(key='list_info_data')
    load_dotenv()

    DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
    host = os.getenv('HOST')
    # port = os.getenv('PORT')
    database = os.getenv('DATABASE')
    username = os.getenv('USERNAME')
    password = os.getenv('PASSWORD')

    try:
        # DB Connection 생성
        conn = pymysql.connect(host=host, user=username, passwd=password, db=database, use_unicode=True, charset='utf8')
        cursor = conn.cursor()

    except Exception as e:
        print(e)
    
    # 데이터 적재
    for x in data:
        duty_addr = x.get('dutyAddr' , '')
        duty_emcls = x.get('dutyEmcls', '')
        duty_emcls_name = x.get('dutyEmclsName', '')
        duty_name = x.get('dutyName', '')
        duty_tel1 = x.get('dutyTel1', '')
        duty_tel3 = x.get('dutyTel3', '')
        hpid = x.get('hpid', '')
        phpid = x.get('phpid', '')
        wgs_84_lat = x.get('wgs84Lat', '')
        wgs_84_lon = x.get('wgs84Lon', '')

        query = f"INSERT INTO HOSPITAL_BASIC_INFO (hpid, phpid, duty_emcls, duty_emcls_name, duty_addr, duty_name, duty_tel1, duty_tel3, wgs_84_lon, wgs_84_lat, center_type)" \
                f" VALUES ('{hpid}', '{phpid}', '{duty_emcls}', '{duty_emcls_name}', '{duty_addr}', '{duty_name}', '{duty_tel1}', '{duty_tel3}', '{wgs_84_lon}', '{wgs_84_lat}', 1)"
        print(query)
        cursor.execute(query)
    conn.commit()  

# 각 API 호출 태스크 생성
list_api_urls = [
    'http://apis.data.go.kr/B552657/ErmctInfoInqireService/getEgytListInfoInqire',
    'http://apis.data.go.kr/B552657/ErmctInfoInqireService/getStrmListInfoInqire'
]

api_tasks = []
for i, api_url in enumerate(list_api_urls):
    api_task = PythonOperator(
        task_id=f'call_api_task_{i}',
        python_callable=call_api,
        op_args=[api_url],
        provide_context=True,
        dag=dag,
    )
    api_tasks.append(api_task)

# 데이터 적재 태스크 생성
load_to_rds_task = PythonOperator(
    task_id='load_to_rds_task',
    python_callable=load_data_to_rds,
    provide_context=True,
    dag=dag,
)

# 의존성 설정
for api_task in api_tasks:
    api_task >> load_to_rds_task
    