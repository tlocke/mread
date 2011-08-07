import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'django-settings'

from google.appengine.dist import use_library
use_library('django', '1.2')
from django.conf import settings
try:
    settings.configure(INSTALLED_APPS=('nothing',))
except:
    pass 
from google.appengine.api import mail
from google.appengine.ext.webapp.util import run_wsgi_app
from monad import Monad, MonadHandler
import datetime
import mread
import django.template


class Cron(Monad, MonadHandler):
    def __init__(self):
        Monad.__init__(self, {'/cron': self, '/cron/reminders': Reminders()})

    def page_fields(self, inv):
        return {}

    def http_get(self, inv):
        return inv.send_ok(self.page_fields(inv))


class Reminders(MonadHandler):    
    def http_get(self, inv):
        now = datetime.datetime.now()
        for meter in mread.Meter.gql("where next_reminder != null and next_reminder <= :1", now):
            body=django.template.Template("""
Hi,

This is a reminder from MtrHub to read your {{ meter.utility.id }} meter {{ meter.name }}. To change the settings, log in to:

http://www.mtrhub.com/

Regards,

MtrHub.
""").render(django.template.Context({'meter': meter}))
            mail.send_mail(sender="MtrHub <mtrhub@mtrhub.com>", to=meter.email_address,
                           subject="MtrHub: Remember to take a meter reading.", body=body)
            meter.set_next_reminder()
            meter.put()
        return inv.send_ok({})

app = Cron()

def main():
    run_wsgi_app(app)

if __name__ == "__main__":
    main()