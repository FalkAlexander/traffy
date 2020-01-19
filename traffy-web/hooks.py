import multiprocessing
import web

#workers = multiprocessing.cpu_count() * 2 + 1
timeout = 120

def on_starting(server):
    web.startup()

def on_exit(server):
    web.shutdown()

