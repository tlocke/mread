import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'django-settings'

from google.appengine.dist import use_library
use_library('django', '1.2')
from django.conf import settings
try:
    settings.configure(INSTALLED_APPS=('nothing',))
except:
    pass 
from google.appengine.api import users
from google.appengine.ext.webapp.util import run_wsgi_app
from monad import Monad, NotFoundException, MonadHandler, UserException, UnauthorizedException, ForbiddenException
from google.appengine.ext import db
import datetime
import csv
import dateutil.relativedelta


class Reader(db.Model):
    name = db.StringProperty(required=True, default='Me')
    openids = db.StringListProperty(required=True)
    
    @staticmethod
    def get_reader():
        user = users.get_current_user()
        if user is None:
            return None
        else:
            return Reader.gql("where openids = :1", user.nickname()).get()
        
    @staticmethod
    def require_reader():
        reader = Reader.get_reader()
        if reader is None:
            raise UnauthorizedException()
        return reader
    
    def get_meter(self, key):
        meter = Meter.get(key)
        if self.key() != meter.reader.key():
            raise ForbiddenException()
        return meter


class ReaderView(MonadHandler):
    def http_get(self, inv):
        reader_key = inv.get_string("reader_key")
        reader = Reader.get_reader(reader_key)
        current_reader = Reader.require_reader()            
        if current_reader.key() != reader.key():
            raise ForbiddenException()

        return inv.send_ok({'reader': reader })
    

class Meter(db.Expando):
    reader = db.ReferenceProperty(Reader)
    email_address = db.EmailProperty()
    reminder_frequency = db.StringProperty()
    last_reminder = db.DateTimeProperty()
    is_public = db.BooleanProperty(default=False, required=True)
    name = db.StringProperty(default='House', required=True)
    
    @staticmethod
    def get_meter(key):
        meter = Meter.get(key)
        if meter is None:
            raise NotFoundException()
        return meter
    
    def set_reminder(self, email_address, reminder_frequency):
        self.email_address = email_address
        self.reminder_frequency = reminder_frequency
        
    
class Read(db.Model, MonadHandler):
    read_date = db.DateTimeProperty(required=True)
    meter = db.ReferenceProperty(Meter)
    kwh = db.FloatProperty(required=True)

    @staticmethod
    def get_read(key):
        read = Read.get(key)
        if read is None:
            raise NotFoundException()
        return read
    
    def update(self, read_date, kwh):
        self.read_date = read_date
        self.kwh = kwh
        self.put()


class MRead(Monad, MonadHandler):
    def __init__(self):
        Monad.__init__(self, {'/': self, '/_ah/login_required': LogIn(), '/log-in': LogIn(), '/meter': MeterView(), '/read': ReadView(), '/upload': UploadView(), '/chart': ChartView(), '/meter-settings': MeterSettings(), '/reader': ReadView(), '/edit-reader': EditReader()})
        # Copy to reader
        '''
        for editor in Editor.all():
            reader = Reader(name=editor.name, openids=[editor.openid])
            reader.put()
        
        for meter in Meter.all():
            delattr(meter, 'editor')
            meter.put()
        '''    
        
    def page_fields(self, inv):
        fields = {'meters': Meter.gql("where is_public = TRUE").fetch(30), 'realm': inv.home_url()}
        
        user = users.get_current_user()
        if user is not None:
            reader = Reader.get_reader()
            if reader is None:
                reader = Reader(openids=[user.nickname()])
                reader.put()
                meter = Meter(reader=reader)
                meter.put()
            fields['current_reader'] = reader
            fields['meter'] = Meter.gql("where reader = :1", reader).get()
        return fields

    def http_get(self, inv):
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
                providers.append({'name': name, 'url': users.create_login_url(dest_url="/", federated_identity=url)})
        return fields
    
    
class MeterView(MonadHandler):
    def http_get(self, inv):
        meter_key = inv.get_string("meter_key")
        meter = Meter.get_meter(meter_key)
        if meter.is_public:
            current_reader = Reader.get_reader()
        else:
            current_reader = Reader.require_reader()            
            if current_reader.key() != meter.reader.key():
                raise ForbiddenException()
        return inv.send_ok(self.page_fields(meter, current_reader))


    def http_post(self, inv):
        try:
            reader = Reader.require_reader()
            meter_key = inv.get_string("meter_key")
            meter = Meter.get_meter(meter_key)
            if reader.key() != meter.reader.key():
                raise ForbiddenException()
            
            if inv.has_control('settings'):
                is_public = inv.has_control('is_public')
                email_address = inv.get_string('email_address')
                frequency = inv.get_string('reminder_frequency')
                meter.set_reminder(email_address, frequency)
                meter.is_public = is_public
                meter.put()
                fields = self.page_fields(meter, reader)
                fields['message'] = 'Settings updated successfully.'
                return inv.send_ok(fields)
            else:
                read_date = inv.get_datetime("read")
                kwh = inv.get_float("kwh")
                read = Read(meter=meter, read_date=read_date, kwh=kwh)
                read.put()
                fields = self.page_fields(meter, reader)
                fields['message'] = 'Read added successfully.'
                return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(meter, reader)
            raise e

    def page_fields(self, meter, current_reader):
        reads = Read.gql("where meter = :1 order by read_date desc", meter).fetch(30)
        now_datetime = datetime.datetime.now()
        now = {'year': now_datetime.year, 'month': '0'[len(str(now_datetime.month)) - 1:] + str(now_datetime.month), 'day': '0'[len(str(now_datetime.day)) - 1:] + str(now_datetime.day), 'hour': '0'[len(str(now_datetime.hour)) - 1:] + str(now_datetime.hour), 'minute': '0'[len(str(now_datetime.minute)) - 1:] + str(now_datetime.minute)}
        
        days = ['0'[len(str(day)) - 1:] + str(day) for day in range(1,32)]        
        months = ['0'[len(str(month)) - 1:] + str(month) for month in range(1,13)]
        hours = ['0'[len(str(hour)) - 1:] + str(hour) for hour in range(24)]
        minutes = ['0'[len(str(minute)) - 1:] + str(minute) for minute in range(60)]

        return {'current_reader': current_reader, 'meter': meter, 'reads': reads, 'months': months, 'days': days, 'hours': hours, 'minutes': minutes, 'now':now}


class MeterSettings(MonadHandler):
    def http_get(self, inv):
        meter_key = inv.get_string("meter_key")
        meter = Meter.get_meter(meter_key)
        reader = Reader.require_reader()            
        if reader.key() != meter.reader.key():
            raise ForbiddenException()
        return inv.send_ok(self.page_fields(meter, reader))


    def http_post(self, inv):
        try:
            reader = Reader.require_reader()
            meter_key = inv.get_string("meter_key")
            meter = Meter.get_meter(meter_key)
            if reader.key() != meter.reader.key():
                raise ForbiddenException()
            
            is_public = inv.has_control('is_public')
            email_address = inv.get_string('email_address')
            frequency = inv.get_string('reminder_frequency')
            name = inv.get_string('name')

            meter.set_reminder(email_address, frequency)
            meter.is_public = is_public
            meter.name = name
            meter.put()
            fields = self.page_fields(meter, reader)
            fields['message'] = 'Settings updated successfully.'
            return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(meter, reader)
            raise e

    def page_fields(self, meter, editor):
        return {'editor': editor, 'meter': meter}


class EditReader(MonadHandler):
    def http_get(self, inv):
        reader_key = inv.get_string("reader_key")
        reader = Reader.get_reader(reader_key)
        current_reader = Reader.require_reader()       
        if current_reader.key() != reader.key():
            raise ForbiddenException()
        return inv.send_ok(self.page_fields(reader, current_reader))


    def http_post(self, inv):
        try:
            reader = Reader.require_reader()
            meter_key = inv.get_string("meter_key")
            meter = Meter.get_meter(meter_key)
            if reader.key() != meter.reader.key():
                raise ForbiddenException()
            
            is_public = inv.has_control('is_public')
            email_address = inv.get_string('email_address')
            frequency = inv.get_string('reminder_frequency')
            name = inv.get_string('name')

            meter.set_reminder(email_address, frequency)
            meter.is_public = is_public
            meter.name = name
            meter.put()
            fields = self.page_fields(meter, reader)
            fields['message'] = 'Settings updated successfully.'
            return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(meter, reader)
            raise e

    def page_fields(self, editor, current_editor):
        return {'current_editor': editor, 'current_editor': current_editor}



class UploadView(MonadHandler):
    def http_get(self, inv):
        meter_key = inv.get_string('meter_key')
        meter = Meter.get_meter(meter_key)
        if meter.is_public:
            reader = None
        else:
            reader = Reader.require_reader()
            if reader.key() != meter.reader.key():
                raise ForbiddenException()

        return inv.send_ok(self.page_fields(meter, reader))


    def http_post(self, inv):
        try:
            reader = Reader.require_reader()
            meter_key = inv.get_string("meter_key")
            meter = reader.get_meter(meter_key)

            file_item = inv.get_file("spreadsheet")
            if file_item.filename.endswith(".csv"):
                rdr = csv.reader(file_item.file)
                for row in rdr:
                    if len(row) < 2:
                        raise UserException("Expecting 2 fields per row, the date in the format yyyy-MM-dd HH:mm followed by the reading.")
                    try:
                        read_date = datetime.datetime.strptime(row[0].strip(), '%Y-%m-%d %H:%M')
                    except ValueError, e:
                        raise UserException("Problem at line number " + str(rdr.line_num) + " of the file. The first field (the read date field) isn't formatted correctly, it should be of the form 2010-02-23T21:46. " + str(e))
                    kwh = float(row[1].strip())
                    read = Read(meter=meter, read_date=read_date, kwh=kwh)
                    read.put()
                fields = self.page_fields(meter, reader)
                fields['message'] = 'File imported successfully.'
                return inv.send_ok(fields)
            else:
                raise UserException("The file name must end with '.csv.'")
        except UserException, e:
            e.values = self.page_fields(meter, reader)
            raise e

    def page_fields(self, meter, editor):
        return {'editor': editor, 'meter': meter}


class ChartView(MonadHandler):
    def http_get(self, inv):
        return inv.send_ok(self.page_fields(inv))
    
    def kwh(self, meter, start_date, finish_date):
        sum_kwh = 0
        code = 'complete-data'
        first_read = Read.gql("where meter = :1 and read_date <= :2 order by read_date desc", meter, start_date).get()
        if first_read is None:
            code = 'partial-data'
        last_read = Read.gql("where meter = :1 and read_date >= :2 order by read_date", meter, finish_date).get()
        if last_read is None:
            code = 'partial-data'
            q_finish = finish_date
        else:
            q_finish = last_read.read_date
        for read in Read.gql("where meter = :1 and read_date > :2 and read_date <= :3 order by read_date", meter, start_date, q_finish):
            if first_read is not None:
                rate = (read.kwh - first_read.kwh) / self.total_seconds(read.read_date - first_read.read_date)
                sum_kwh += rate * max(self.total_seconds(min(read.read_date, finish_date) - max(first_read.read_date, start_date)), 0)
            first_read = read
        return {'kwh': sum_kwh, 'code': code, 'start_date': start_date, 'finish_date': finish_date}


    def total_seconds(self, td):
        return (td.microseconds + (td.seconds + td.days * 24 * 3600) * 10**6) / 10**6


    def page_fields(self, inv):
        meter_key = inv.get_string("meter_key")
        meter = Meter.get_meter(meter_key)
        now = datetime.datetime.now().date()
        now = datetime.datetime(now.year, now.month, 1)
        months = []
        for month in range(-11, 1):
            month_start = now + dateutil.relativedelta.relativedelta(months=month)
            month_finish = month_start + dateutil.relativedelta.relativedelta(months=1)
            #sys.stderr.write("month start " + str(month_start) + " month finish " + str(month_finish))
            months.append(self.kwh(meter, month_start, month_finish))
        
        chd = [month['kwh'] for month in months]
        labels = [datetime.datetime.strftime(month['start_date'], '%b %Y') for month in months]
        return {'editor': Reader.get_reader(), 'meter': meter, 'months': months, 'data': ','.join(str(datum) for datum in chd), 'max_data': str(max(chd)), 'labels': '|'.join(labels)}


class ReadView(MonadHandler):
    def http_get(self, inv):
        return inv.send_ok(self.page_fields(inv))

    def http_post(self, inv):
        try:
            reader = Reader.get_reader()
            if reader is None:
                raise UnauthorizedException()
            read_key = inv.get_string("read_key")
            read = Read.get_read(read_key)
            meter = read.meter
            if reader.key() != meter.reader.key():
                raise ForbiddenException()
            
            if inv.has_control("delete"):
                read.delete()
                return inv.send_see_other("/meter?meter_key=" + str(meter.key()))
            else:
                read_date = inv.get_datetime("read")
                kwh = inv.get_float("kwh")
                read.update(read_date, kwh)
                fields = self.page_fields(inv)
                fields['message'] = 'Read edited successfully.'
                return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(inv)
            raise e

    def page_fields(self, inv):
        read_key = inv.get_string("read_key")
        read = Read.get_read(read_key)
        
        days = [{'display': '0'[len(str(day)) - 1:] + str(day), 'number': day} for day in range(1,32)]        
        months = [{'display': '0'[len(str(month)) - 1:] + str(month), 'number': month} for month in range(1,13)]
        hours = [{'display': '0'[len(str(hour)) - 1:] + str(hour), 'number': hour} for hour in range(24)]
        minutes = [{'display': '0'[len(str(minute)) - 1:] + str(minute), 'number': minute} for minute in range(60)]

        return {'reader': Reader.get_reader(), 'read': read, 'months': months, 'days': days, 'hours': hours, 'minutes': minutes}
    
    
class MetersView(MonadHandler):
    def http_get(self, inv):
        meters = Meter.gql("where tags = 'public'").fetch(30)
        fields = {'meters': meters}
        user = users.get_current_user()
        if user is not None:
            fields['user'] = user
            fields['meter'] = Meter.gql("where user = :1", user).fetch(1)
        return inv.send_ok(fields)



app = MRead()

def main():
    run_wsgi_app(app)

if __name__ == "__main__":
    main()