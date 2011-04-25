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
    proposed_openid = db.StringProperty(required=False, default='')
    
    @staticmethod
    def get_current_reader():
        user = users.get_current_user()
        if user is None:
            return None
        else:
            return Reader.gql("where openids = :1", user.nickname()).get()
    
    @staticmethod
    def get_reader(reader_key):
        reader = Reader.get(reader_key)
        if reader is None:
            raise NotFoundException()
        return reader
    
    
    @staticmethod
    def require_current_reader():
        reader = Reader.get_current_reader()
        if reader is None:
            raise UnauthorizedException()
        return reader


class ReaderView(MonadHandler):
    def http_get(self, inv):
        reader_key = inv.get_string("reader_key")
        reader = Reader.get_reader(reader_key)
        current_reader = Reader.require_current_reader()            
        if current_reader.key() != reader.key():
            raise ForbiddenException()

        return inv.send_ok({'reader': reader, 'current_reader': current_reader})
    

class Meter(db.Model):
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
        Monad.__init__(self, {'/': self, '/_ah/login_required': SignIn(), '/sign-in': SignIn(), '/meter': MeterView(), '/read': ReadView(), '/upload': UploadView(), '/chart': ChartView(), '/meter-settings': MeterSettings(), '/reader': ReaderView(), '/reader-settings': ReaderSettings(), '/welcome': Welcome(), '/export-reads': ExportReads()})
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
        fields = {'meters': Meter.gql("where is_public = TRUE").fetch(30)}
        
        user = users.get_current_user()
        if user is not None:
            current_reader = Reader.get_current_reader()
            if current_reader is not None:
                fields['current_reader'] = current_reader
                fields['meter'] = Meter.gql("where reader = :1", current_reader).get()
        return fields

    def http_get(self, inv):
        return inv.send_ok(self.page_fields(inv))


class SignIn(MonadHandler):
    def http_get(self, inv):
        if users.get_current_user() is None:
            providers = []
            fields = {'providers': providers, 'home_url': inv.home_url()}
            for url, name in {'google.com/accounts/o8/id': 'Google', 'yahoo.com': 'Yahoo', 'myspace.com': 'MySpace', 'aol.com': 'AOL', 'myopenid.com': 'MyOpenID'}.iteritems():
                providers.append({'name': name, 'url': users.create_login_url(dest_url="/welcome", federated_identity=url)})
 
            return inv.send_ok(fields)
        else:
            return inv.send_found('/welcome')


class Welcome(MonadHandler):
    def http_get(self, inv):
        user = users.get_current_user()
        if user is None:
            return inv.send_ok(self.page_fields(None, None))
        else:
            current_reader = Reader.get_current_reader()
            if current_reader is None:
                fields = self.page_fields(None, None)
                proposed_readers = Reader.gql("where proposed_openid = :1", user.nickname()).fetch(10)
                if len(proposed_readers) > 0:
                    fields['proposed_readers'] = proposed_readers
                return inv.send_ok(fields)
            else:            
                return inv.send_found('/')

    def http_post(self, inv):
        user = users.get_current_user()
        if user is None:
            raise UnauthorizedException()
        
        if inv.has_control('associate'):
            current_reader = Reader.get_current_reader()
            if current_reader is None:
                reader_key = inv.get_string('reader_key')
                reader = Reader.get_reader(reader_key)
                if reader.proposed_openid == user.nickname():
                    reader.proposed_openid = ''
                    reader.openids.append(user.nickname())
                    reader.put()
                    current_reader = Reader.get_current_reader()
                    meter = Meter.gql("where reader = :1", current_reader).get()
                    fields = self.page_fields(current_reader, meter)
                    fields['message'] = 'The OpenId ' + user.nickname() + ' has been successfully associated with the reader ' + reader.name + '.'
                    inv.send_ok(fields)
                else:
                    e = UserException("Can't associate " + user.nickname() + " with the account " + reader.name + " because the OpenId you're signed in with doesn't match the proposed OpenId.")
                    e.values = self.page_fields(None, None)
                    raise e
            else:
                meter = Meter.gql("where reader = :1", current_reader).get()
                e = UserException("The OpenId " + user.nickname() + " is already associated with an account.")
                e.values = self.page_fields(current_reader, meter) 
                raise e
        else:
            current_reader = Reader.get_current_reader()
            if current_reader is None:
                current_reader = Reader(openids=[user.nickname()])
                current_reader.put()
            
            meter = Meter.gql("where reader = :1", current_reader).get()
            if meter is None:
                meter = Meter(reader=current_reader)
                meter.put()
        
            return inv.send_ok(self.page_fields(current_reader, meter))

        
    def page_fields(self, current_reader, meter):
        return {'current_reader': current_reader, 'meter': meter}

    
class MeterView(MonadHandler):
    def http_get(self, inv):
        meter_key = inv.get_string("meter_key")
        meter = Meter.get_meter(meter_key)
        if meter.is_public:
            current_reader = Reader.get_current_reader()
        else:
            current_reader = Reader.require_current_reader()            
            if current_reader.key() != meter.reader.key():
                raise ForbiddenException()
        return inv.send_ok(self.page_fields(meter, current_reader))


    def http_post(self, inv):
        try:
            current_reader = Reader.require_current_reader()
            meter_key = inv.get_string("meter_key")
            meter = Meter.get_meter(meter_key)
            if current_reader.key() != meter.reader.key():
                raise ForbiddenException()
            
            if inv.has_control('settings'):
                is_public = inv.has_control('is_public')
                email_address = inv.get_string('email_address')
                frequency = inv.get_string('reminder_frequency')
                meter.set_reminder(email_address, frequency)
                meter.is_public = is_public
                meter.put()
                fields = self.page_fields(meter, current_reader)
                fields['message'] = 'Settings updated successfully.'
                return inv.send_ok(fields)
            else:
                read_date = inv.get_datetime("read")
                kwh = inv.get_float("kwh")
                read = Read(meter=meter, read_date=read_date, kwh=kwh)
                read.put()
                fields = self.page_fields(meter, current_reader)
                fields['message'] = 'Read added successfully.'
                return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(meter, current_reader)
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


class ExportReads(MonadHandler):
    def http_get(self, inv):
        meter_key = inv.get_string("meter_key")
        meter = Meter.get_meter(meter_key)
        if meter.is_public:
            current_reader = Reader.get_current_reader()
        else:
            current_reader = Reader.require_current_reader()            
            if current_reader.key() != meter.reader.key():
                raise ForbiddenException()

        reads = Read.gql("where meter = :1 order by read_date desc", meter).fetch(1000)
        return inv.send_ok({'reads': reads, 'template-name': 'export_reads.csv', 'content-type': 'text/csv', 'content-disposition': 'attachment; filename=reads.csv;'})


class MeterSettings(MonadHandler):
    def http_get(self, inv):
        meter_key = inv.get_string("meter_key")
        meter = Meter.get_meter(meter_key)
        reader = Reader.require_current_reader()            
        if reader.key() != meter.reader.key():
            raise ForbiddenException()
        return inv.send_ok(self.page_fields(meter, reader))


    def http_post(self, inv):
        try:
            current_reader = Reader.require_current_reader()
            meter_key = inv.get_string("meter_key")
            meter = Meter.get_meter(meter_key)
            if current_reader.key() != meter.reader.key():
                raise ForbiddenException()
            
            is_public = inv.has_control('is_public')
            email_address = inv.get_string('email_address')
            frequency = inv.get_string('reminder_frequency')
            name = inv.get_string('name')

            meter.set_reminder(email_address, frequency)
            meter.is_public = is_public
            meter.name = name
            meter.put()
            fields = self.page_fields(meter, current_reader)
            fields['message'] = 'Settings updated successfully.'
            return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(meter, current_reader)
            raise e

    def page_fields(self, meter, current_reader):
        return {'current_reader': current_reader, 'meter': meter}


class ReaderSettings(MonadHandler):
    def http_get(self, inv):
        reader_key = inv.get_string("reader_key")
        reader = Reader.get_reader(reader_key)
        current_reader = Reader.require_current_reader()       
        if current_reader.key() != reader.key():
            raise ForbiddenException()
        return inv.send_ok(self.page_fields(reader))


    def http_post(self, inv):
        try:
            current_reader = Reader.require_current_reader()
            reader_key = inv.get_string("reader_key")
            reader = Reader.get_reader(reader_key)
            if current_reader.key() != reader.key():
                raise ForbiddenException()

            if inv.has_control('delete_openid'):
                pass
            elif inv.has_control('propose_openid'):
                proposed_openid = inv.get_string('proposed_openid')
                reader.proposed_openid = proposed_openid.strip()
                reader.put()
                fields = self.page_fields(reader)
                if len(proposed_openid) == 0:
                    fields['message'] = 'Proposed OpenId successfully set to blank.'
                else:
                    fields['message'] = 'Proposed OpenId set successfully. Now sign out and then sign in using the proposed OpenId'
                return inv.send_ok(fields)
            elif inv.has_control('delete'):
                for meter in Meter.gql("where reader = :1", reader):
                    for read in Read.gql("where meter = :1", meter):
                        read.delete()
                    meter.delete
                reader.delete()
                return inv.send_found('/welcome')
            else:
                name = inv.get_string('name')
                reader.name = name
                reader.put()
                fields = self.page_fields(reader)
                fields['message'] = 'Settings updated successfully.'
                return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(reader)
            raise e

    def page_fields(self, reader):
        return {'reader': reader, 'current_reader': reader}



class UploadView(MonadHandler):
    def http_get(self, inv):
        meter_key = inv.get_string('meter_key')
        meter = Meter.get_meter(meter_key)
        current_reader = Reader.require_current_reader()
        if current_reader.key() != meter.reader.key():
            raise ForbiddenException()

        return inv.send_ok(self.page_fields(meter, current_reader))


    def http_post(self, inv):
        try:
            current_reader = Reader.require_current_reader()
            meter_key = inv.get_string("meter_key")
            meter = Meter.get_meter(meter_key)
            if current_reader.key() != meter.reader.key():
                raise ForbiddenException()

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
                fields = self.page_fields(meter, current_reader)
                fields['message'] = 'File imported successfully.'
                return inv.send_ok(fields)
            else:
                raise UserException("The file name must end with '.csv.'")
        except UserException, e:
            e.values = self.page_fields(meter, current_reader)
            raise e

    def page_fields(self, meter, current_reader):
        return {'current_reader': current_reader, 'meter': meter}


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
        return {'current_reader': Reader.get_current_reader(), 'meter': meter, 'months': months, 'data': ','.join(str(datum) for datum in chd), 'max_data': str(max(chd)), 'labels': '|'.join(labels)}


class ReadView(MonadHandler):
    def http_get(self, inv):
        current_reader = Reader.get_current_reader()
        read_key = inv.get_string("read_key")
        read = Read.get_read(read_key)
        meter = read.meter
        if meter.is_public:
            return inv.send_ok(self.page_fields(current_reader, read))
        elif current_reader is None:
            raise UnauthorizedException()
        elif current_reader.key() == meter.reader.key():
            return inv.send_ok(self.page_fields(current_reader, read))
        else:
            raise ForbiddenException()

  
    def http_post(self, inv):
        try:
            current_reader = Reader.require_current_reader()
            read_key = inv.get_string("read_key")
            read = Read.get_read(read_key)
            meter = read.meter
            if current_reader.key() != meter.reader.key():
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
            e.values = self.page_fields(current_reader, read)
            raise e

    def page_fields(self, current_reader, read):      
        days = [{'display': '0'[len(str(day)) - 1:] + str(day), 'number': day} for day in range(1,32)]        
        months = [{'display': '0'[len(str(month)) - 1:] + str(month), 'number': month} for month in range(1,13)]
        hours = [{'display': '0'[len(str(hour)) - 1:] + str(hour), 'number': hour} for hour in range(24)]
        minutes = [{'display': '0'[len(str(minute)) - 1:] + str(minute), 'number': minute} for minute in range(60)]

        return {'current_reader': current_reader, 'read': read, 'months': months, 'days': days, 'hours': hours, 'minutes': minutes}


app = MRead()

def main():
    run_wsgi_app(app)

if __name__ == "__main__":
    main()