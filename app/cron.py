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
import dateutil.relativedelta
import mread


class Cron(Monad, MonadHandler):
    def __init__(self):
        Monad.__init__(self, {'/cron': self, '/cron/reminders': Reminders()})

    def page_fields(self, inv):
        return {}

    def http_get(self, inv):
        return inv.send_ok(self.page_fields(inv))


class Reminders(MonadHandler):
    def http_get(self, inv):
        msg = mail.EmailMessage(sender="MtrHub Support <tlocke@tlocke.org.uk>",
                                subject="MtrHub: Remember to take a meter reading.",
                                body="""
Hi,

This is a reminder from MtrHub to read your meter. To change the settings, log in to:

http://www.mtrhub.com/

Regards,

MtrHub.
""")
        now = datetime.datetime.now()
        for period_text, period in [('monthly', dateutil.relativedelta.relativedelta(months=1)), ('weekly', dateutil.relativedelta.relativedelta(weeks=1))]:
            for meter in mread.Meter.gql("where reminder_frequency = :1 and last_reminder < :2", period_text, now - period):
                msg.initialize(to=meter.email_address)
                msg.Send()
                meter.last_reminder = now
                meter.put()

        return inv.send_ok({})

app = Cron()

def main():
    run_wsgi_app(app)

if __name__ == "__main__":
    main()