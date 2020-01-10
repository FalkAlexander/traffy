import multiprocessing
import traffy

workers = multiprocessing.cpu_count() * 2 + 1
timeout = 120

def on_starting(server):
    traffy.startup()

def on_exit(server):
    traffy.shutdown()

