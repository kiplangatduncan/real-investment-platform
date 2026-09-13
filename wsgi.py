import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

application = get_wsgi_application()
from app import app

if __name__ == "__main__":
    app.run()
  
from app import create_app

app = create_app()
