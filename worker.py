from rq import Worker, Queue
from redis import Redis

# Настройка подключения к Redis
redis_conn = Redis(host='localhost', port=6379, db=0)
queue = Queue(connection=redis_conn)

if __name__ == "__main__":
    worker = Worker([queue], connection=redis_conn)
    worker.work()
