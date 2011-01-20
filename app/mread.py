from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app
from monad import Monad, NotFoundException, MonadHandler, UserException, UnauthorizedException, ForbiddenException
from google.appengine.ext import db
import sys
import datetime


class Editor(db.Model):
    openid = db.StringProperty(required=True)
    
    @staticmethod
    def get_editor():
        user = users.get_current_user()
        if user is None:
            return None
        else:
            return Editor.gql("where openid = :1", user.nickname()).get()


class EditorView(MonadHandler):
    def http_get(self, inv):
        return inv.send_ok({'editor': self})
    

class Meter(db.Model):
    tags = db.StringListProperty()
    editor = db.ReferenceProperty(Editor)
    
    @staticmethod
    def get_meter(key):
        meter = Meter.get(key)
        if meter is None:
            raise NotFoundException()
        return meter


class Read(db.Model, MonadHandler):
    read_date = db.DateTimeProperty(required=True)
    meter = db.ReferenceProperty(Meter)
    kwh = db.FloatProperty(required=True)

  
class MRead(Monad, MonadHandler):
    def __init__(self):
        Monad.__init__(self, {'/': self, '/log-in': LogIn(), '/meter': MeterView()})

    def page_fields(self, inv):
        meters = Meter.gql("where tags = 'public'").fetch(30)
        fields = {'meters': meters}
        
        fields['realm'] = inv.home_url()
        user = users.get_current_user()
        if user is not None:
            editor = Editor.get_editor()
            if editor is None:
                editor = Editor(openid=user.nickname())
                editor.put()
                meter = Meter(editor=editor)
                meter.put()
            fields['editor'] = editor
            fields['meter'] = Meter.gql("where editor = :1", editor).get()
        return fields

    def http_get(self, inv):
        return inv.send_ok(self.page_fields(inv))
    
    def http_post(self, inv):
        inv.log_out()
        return inv.send_ok(self.page_fields(inv))


class LogIn(MonadHandler):
    def http_get(self, inv):
        return inv.send_ok(self.page_fields())
    
    def page_fields(self):
        fields = {}            
        user = users.get_current_user()
        if user is None:
            providers = []
            fields['providers'] = providers
            for url, name in {'google.com/accounts/o8/id': 'Google', 'yahoo.com': 'Yahoo', 'myspace.com': 'MySpace', 'aol.com': 'AOL', 'myopenid.com': 'MyOpenID'}.iteritems():
                sys.stderr.write("the url is " + url + "The name is " + name)
                providers.append({'name': name, 'url': users.create_login_url(dest_url="/", federated_identity=url)})
        return fields
    
    
class MeterView(MonadHandler):
    def http_get(self, inv):
        return inv.send_ok(self.page_fields(inv))

    def http_post(self, inv):
        try:
            editor = Editor.get_editor()
            if editor is None:
                raise UnauthorizedException()
            meter_key = inv.get_string("meter-key")
            meter = Meter.get_meter(meter_key)
            if editor.key() != meter.editor.key():
                raise ForbiddenException()
            read_date = inv.get_datetime("read")
            kwh = inv.get_float("kwh")
            read = Read(meter=meter, read_date=read_date, kwh=kwh)
            read.put()
            fields = self.page_fields(inv)
            fields['message'] = 'Read added successfully.'
            return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(inv)
            raise e

    def page_fields(self, inv):
        meter_key = inv.get_string("meter-key")
        meter = Meter.get_meter(meter_key)

        reads = Read.gql("where meter = :1 order by read_date desc", meter).fetch(30)
        now_datetime = datetime.datetime.now()
        now = {'year': now_datetime.year, 'month': '0'[len(str(now_datetime.month)) - 1:] + str(now_datetime.month), 'day': '0'[len(str(now_datetime.day)) - 1:] + str(now_datetime.day), 'hour': '0'[len(str(now_datetime.hour)) - 1:] + str(now_datetime.hour), 'minute': '0'[len(str(now_datetime.minute)) - 1:] + str(now_datetime.minute)}
        
        days = ['0'[len(str(day)) - 1:] + str(day) for day in range(1,32)]        
        months = ['0'[len(str(month)) - 1:] + str(month) for month in range(1,13)]
        hours = ['0'[len(str(hour)) - 1:] + str(hour) for hour in range(24)]
        minutes = ['0'[len(str(minute)) - 1:] + str(minute) for minute in range(60)]

        return {'editor': Editor.get_editor(), 'meter': meter, 'reads': reads, 'months': months, 'days': days, 'hours': hours, 'minutes': minutes, 'now':now}
    
    
class MetersView(MonadHandler):
    def http_get(self, inv):
        meters = Meter.gql("where tags = 'public'").fetch(30)
        fields = {'meters': meters}
        user = users.get_current_user()
        if user is not None:
            fields['user'] = user
            fields['meter'] = Meter.gql("where user = :1", user).fetch(1)
        return inv.send_ok(fields)


class Editors(MonadHandler):
    def http_get(self, inv):
        return inv.send_ok({'editors': Editor.all().fetch(100)})

    def child(self, path_element):
        editor = Editor.get_by_key_name('p' + path_element)
        if editor is None:
            raise NotFoundException()
        return editor


def main():
    run_wsgi_app(MRead())

if __name__ == "__main__":
    main()