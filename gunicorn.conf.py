workers = 1
worker_class = 'eventlet'
bind = '0.0.0.0:$PORT'
daemon = False
name = 'health_tracker'
accesslog = '-'
errorlog = '-'
timeout = 120 