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
        msg = mail.EmailMessage(sender="MtrHub Support <support@mtrhub.com>",
                                subject="MtrHub: Remember to take a meter reading.",
                                body="""
Hi,

This is a reminder from MtrHub to read your meter. To change the settings, log in to:

http://www.mtrhub.com/

Regards,

MtrHub.
""")
        now = datetime.datetime.now()
        for meter in mread.Meter.gql("where reminder_frequency = 'monthly' and last_reminder < :1", now - dateutil.relativedelta.relativedelta(months=1)):
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