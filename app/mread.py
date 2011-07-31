import os
os.environ['DJANGO_SETTINGS_MODULE'] = 'django-settings'

from google.appengine.dist import use_library
use_library('django', '1.2')
from django.conf import settings
try:
    settings.configure(INSTALLED_APPS=('nothing',))
except:
    pass
from google.appengine.api import users, mail
from google.appengine.ext.webapp.util import run_wsgi_app
from monad import Monad, NotFoundException, MonadHandler, UserException, UnauthorizedException, ForbiddenException
from google.appengine.ext import db
import datetime
import csv
import dateutil.relativedelta
import dateutil.rrule
import pytz
import django.template


UTILITY_DICT = {'electricity': {'id': 'electricity', 'name': 'Electricity', 'units': ['kWh']},
                'water': {'id': 'water', 'name': 'Water', 'units': ['m3']},
                'gas': {'id': 'gas', 'name': 'Gas', 'units': ['m3', 'ft3']}}

UTILITY_IDS = UTILITY_DICT.keys()

UTILITY_LIST = [val for val in UTILITY_DICT.values()]


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
    

FREQS = {'monthly': dateutil.rrule.MONTHLY, 'weekly': dateutil.rrule.WEEKLY}

class Meter(db.Model):
    reader = db.ReferenceProperty(Reader)
    email_address = db.EmailProperty()
    reminder_start = db.DateTimeProperty(default=None)
    reminder_frequency = db.StringProperty(default='never')
    next_reminder = db.DateTimeProperty(default=None)
    is_public = db.BooleanProperty(default=False, required=True)
    name = db.StringProperty(default='House', required=True)
    time_zone = db.StringProperty(default='UTC')
    utility_id = db.StringProperty(default='electricity')
    units = db.StringProperty()
    
    send_read_to = db.EmailProperty()
    send_read_name = db.StringProperty(default='')
    send_read_reader_email = db.EmailProperty()
    send_read_address = db.StringProperty(default='')
    send_read_postcode = db.StringProperty(default='')
    send_read_account = db.StringProperty(default='')
    send_read_msn = db.StringProperty(default='')

    latest_customer_read_date = db.DateTimeProperty(default=None)
    customer_read_frequency = db.StringProperty(default='never')
    
    @staticmethod
    def get_meter(key):
        meter = Meter.get(key)
        if meter is None:
            raise NotFoundException()
        return meter
        
    
    def update(self, utility_id, units, name, tz_name, is_public, email_address, reminder_start, reminder_frequency, customer_read_frequency):
        try:
            utility = UTILITY_DICT[utility_id]
        except KeyError:
            raise UserException("That's not a valid utility id.")
        self.utility_id = utility_id
        if units not in utility['units']:
            raise UserException("Those aren't valid units.")
        self.units = units  
        self.name = name
        try:
            pytz.timezone(tz_name)
            self.time_zone = tz_name
        except KeyError:
            raise UserException("Can't find the time zone " + tz_name)
        self.is_public = is_public
        self.email_address = email_address
        self.reminder_start = reminder_start
        self.reminder_frequency = reminder_frequency
        if self.reminder_frequency == 'never':
            self.next_reminder = None
        elif self.reminder_frequency in FREQS:
            self.set_next_reminder()
        else:
            raise UserException("Reminder frequency not recognized.")
        self.customer_read_frequency = customer_read_frequency
        self.put()
        
    def get_tzinfo(self):
        return pytz.timezone(self.time_zone)
        
    def set_next_reminder(self):
        freq = FREQS[self.reminder_frequency]
        naive_dstart = self.local_reminder_start().replace(tzinfo=None)
        naive_rrule = dateutil.rrule.rrule(freq, dtstart=naive_dstart)
        naive_now = self.get_tzinfo().normalize(pytz.utc.localize(datetime.datetime.now()).astimezone(self.get_tzinfo())).replace(tzinfo=None)
        self.next_reminder = pytz.utc.normalize(self.get_tzinfo().localize(naive_rrule.after(naive_now)).astimezone(pytz.utc))

    def local_next_reminder(self):
        return self.get_tzinfo().normalize(pytz.utc.localize(self.next_reminder).astimezone(self.get_tzinfo()))

    def local_reminder_start(self):
        return self.get_tzinfo().normalize(pytz.utc.localize(self.reminder_start).astimezone(self.get_tzinfo()))

    def utility_name(self):
        return UTILITY_DICT[self.utility_id]['name']
    
    def delete_meter(self):
        for read in Read.gql("where meter = :1", self):
            read.delete()
        self.delete()
        
    def candidate_customer_read(self):
        if self.customer_read_frequency == 'never':
            return None
        
        if self.customer_read_frequency == 'monthly':
            months = 1
        else:
            months = 3
            
        if self.latest_customer_read_date is None:
            cust_date = datetime.datetime(datetime.MINYEAR, 1, 1)
        else:
            cust_date = self.latest_customer_read_date
            
        return Read.gql("where meter = :1 and read_date > :2 order by read_date desc", self, cust_date + dateutil.relativedelta.relativedelta(months=months)).get()
 
                       
class Read(db.Model, MonadHandler):
    read_date = db.DateTimeProperty(required=True)
    meter = db.ReferenceProperty(Meter)
    value = db.FloatProperty(required=True)

    @staticmethod
    def get_read(key):
        read = Read.get(key)
        if read is None:
            raise NotFoundException()
        return read
    
    def update(self, read_date, value):
        if read_date > datetime.datetime.now():
            raise UserException("The read date can't be in the future.")
        self.read_date = read_date
        self.value = value
        self.put()

    def local_read_date(self):
        return self.read_date.replace(tzinfo=pytz.timezone('UTC')).astimezone(pytz.timezone(self.meter.time_zone))        


class MRead(Monad, MonadHandler):
    def __init__(self):
        Monad.__init__(self, {'/': self, '/_ah/login_required': SignIn(), '/sign-in': SignIn(), '/meter': MeterView(), '/read': ReadView(), '/edit-read': EditRead(), '/send-read': SendRead(), '/upload': UploadView(), '/chart': ChartView(), '/meter-settings': MeterSettings(), '/reader': ReaderView(), '/reader-settings': ReaderSettings(), '/welcome': Welcome(), '/export-reads': ExportReads(), '/add-meter': AddMeter()})
        # Copy to reader
        '''
        for editor in Editor.all():
            reader = Reader(name=editor.name, openids=[editor.openid])
            reader.put()
        
        for meter in Meter.all():
            delattr(meter, 'editor')
            meter.put()

        for meter in Meter.all():
            try:
                logging.debug("about to change meter " + str(meter.key()))
                if meter.reminder_frequency not in ['never', '']:
                    meter.reminder_start = meter.last_reminder
                    meter.set_next_reminder()
                    delattr(meter, 'last_reminder')
                    meter.put()
                else:
                    delattr(meter, 'last_reminder')
                    meter.put()
                logging.debug("successfully changed " + str(meter.key()))
            except AttributeError, e:
                logging.debug("problem changing" + str(e))

        for read in Read.all():
            read.value = read.kwh
            delattr(read, 'kwh')
            read.put()

        for meter in Meter.all():
            try:
                delattr(meter, 'last_reminder')
                meter.put()
            except AttributeError:
                pass
        
        for meter in Meter.all():
            meter.units = UTILITY_DICT[meter.utility_id]['units'][0]
            meter.put()
        '''

    def page_fields(self, inv):
        meters = {}
        public_reads = []
        
        for read in Read.gql("order by read_date desc"):
            meter = read.meter
            if not meter.is_public or str(meter.key()) in meters:
                continue
            meters[str(meter.key())] = meter
            public_reads.append(read)
            if len(public_reads) > 20:
                break
        
        fields = {'public_reads': public_reads}  
        user = users.get_current_user()
        if user is not None:
            current_reader = Reader.get_current_reader()
            if current_reader is not None:
                fields['current_reader'] = current_reader
                reader_meters = Meter.gql("where reader = :1", current_reader).fetch(10)
                fields['meters'] = reader_meters
                fields['candidate_customer_reads'] = [cand for cand in [meter.candidate_customer_read() for meter in reader_meters] if cand is not None]
        return fields

    def http_get(self, inv):
        return inv.send_ok(self.page_fields(inv))


class SignIn(MonadHandler):
    def http_get(self, inv):
        if users.get_current_user() is None:
            if inv.has_control('free-openid'):
                try:
                    openid = inv.get_string('openid_identifier')
                except UserException, e:
                    e.values = self.page_fields()
                    raise e
                    
                return inv.send_found(users.create_login_url(dest_url="/welcome", federated_identity=openid))
            else: 
                return inv.send_ok(self.page_fields())
        else:
            return inv.send_found('/welcome')

    def page_fields(self):
        fields = {'providers': []}
        for url, name, img_name in [('google.com/accounts/o8/id', 'Google', 'google'), ('yahoo.com', 'Yahoo', 'yahoo'), ('myspace.com', 'MySpace', 'myspace'), ('aol.com', 'AOL', 'aol'), ('myopenid.com', 'MyOpenID', 'myopenid')]:
            fields['providers'].append({'name': name, 'url': users.create_login_url(dest_url="/welcome", federated_identity=url), 'img_name': img_name})
        return fields


class Welcome(MonadHandler):
    def http_get(self, inv):
        user = users.get_current_user()
        if user is None:
            return inv.send_ok(self.page_fields(None))
        else:
            current_reader = Reader.get_current_reader()
            if current_reader is None:
                fields = self.page_fields(None)
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
                    fields = self.page_fields(current_reader)
                    fields['message'] = 'The OpenId ' + user.nickname() + ' has been successfully associated with the reader ' + reader.name + '.'
                    return inv.send_ok(fields)
                else:
                    e = UserException("Can't associate " + user.nickname() + " with the account " + reader.name + " because the OpenId you're signed in with doesn't match the proposed OpenId.")
                    e.values = self.page_fields(None)
                    raise e
            else:
                e = UserException("The OpenId " + user.nickname() + " is already associated with an account.")
                e.values = self.page_fields(current_reader) 
                raise e
        else:
            current_reader = Reader.get_current_reader()
            if current_reader is None:
                current_reader = Reader(openids=[user.nickname()])
                current_reader.put()
                message = "Account created successfully."
            else:
                message = None
            
            fields = self.page_fields(current_reader)
            if message is not None:
                fields['message'] = message
            return inv.send_ok(fields)

        
    def page_fields(self, current_reader):
        meters = Meter.gql("where reader = :1", current_reader).fetch(10)
        return {'current_reader': current_reader, 'meters': meters}

    
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
            
            read_date = inv.get_datetime("read", meter.get_tzinfo())
            value = inv.get_float("value")
            read = Read(meter=meter, read_date=read_date, value=value)
            read.put()
            fields = self.page_fields(meter, current_reader)
            fields['read'] = read.key()
            return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(meter, current_reader)
            raise e

    def page_fields(self, meter, current_reader):
        reads = Read.gql("where meter = :1 order by read_date desc", meter).fetch(30)
        now_datetime = meter.get_tzinfo().localize(datetime.datetime.now())
        now = {'year': now_datetime.year, 'month': '0'[len(str(now_datetime.month)) - 1:] + str(now_datetime.month), 'day': '0'[len(str(now_datetime.day)) - 1:] + str(now_datetime.day), 'hour': '0'[len(str(now_datetime.hour)) - 1:] + str(now_datetime.hour), 'minute': '0'[len(str(now_datetime.minute)) - 1:] + str(now_datetime.minute)}
        
        days = ['0'[len(str(day)) - 1:] + str(day) for day in range(1,32)]        
        months = ['0'[len(str(month)) - 1:] + str(month) for month in range(1,13)]
        hours = ['0'[len(str(hour)) - 1:] + str(hour) for hour in range(24)]
        minutes = ['0'[len(str(minute)) - 1:] + str(minute) for minute in range(60)]

        return {'current_reader': current_reader, 'meter': meter, 'reads': reads, 'months': months, 'days': days, 'hours': hours, 'minutes': minutes, 'now':now, 'candidate_customer_read': meter.candidate_customer_read()}


class AddMeter(MonadHandler):
    def http_get(self, inv):
        current_reader = Reader.require_current_reader()            
        return inv.send_ok(self.page_fields(current_reader))


    def http_post(self, inv):
        try:
            current_reader = Reader.require_current_reader()
            is_public = inv.has_control('is_public')
            reminder_frequency = inv.get_string('reminder_frequency')
            name = inv.get_string('name')
            time_zone = inv.get_string('time_zone')
            reminder_start = inv.get_datetime("reminder_start", pytz.timezone(time_zone))
            utility_units = inv.get_string('utility_units')
            if reminder_frequency == 'never':
                email_address = None
            else:
                email_address = inv.get_string('email_address')
                confirm_email_address = inv.get_string('confirm_email_address')
                email_address = email_address.strip()
                if email_address != confirm_email_address.strip():
                    raise UserException("The email addresses don't match.")
            customer_read_frequency = inv.get_string('customer_read_frequency')
            
            meter = Meter(reader=current_reader, email_address=email_address, reminder_start=reminder_start, reminder_frequency=reminder_frequency, is_public=is_public, name=name, time_zone=time_zone, customer_read_frequency=customer_read_frequency)
            meter.put()
            utility_id, units = utility_units.split('-')
            meter.update(utility_id, units, name, time_zone, is_public, email_address, reminder_start, reminder_frequency, customer_read_frequency)
            fields = self.page_fields(current_reader)
            fields['location'] = '/meter?meter_key=' + str(meter.key())
            return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(current_reader)
            raise e

    def page_fields(self, current_reader):
        reminder_start = datetime.datetime.now()
        reminder_start = {'year': reminder_start.year, 'month': '0'[len(str(reminder_start.month)) - 1:] + str(reminder_start.month), 'day': '0'[len(str(reminder_start.day)) - 1:] + str(reminder_start.day), 'hour': '0'[len(str(reminder_start.hour)) - 1:] + str(reminder_start.hour), 'minute': '0'[len(str(reminder_start.minute)) - 1:] + str(reminder_start.minute)}
        days = ['0'[len(str(day)) - 1:] + str(day) for day in range(1,32)]
        months = ['0'[len(str(month)) - 1:] + str(month) for month in range(1,13)]
        hours = ['0'[len(str(hour)) - 1:] + str(hour) for hour in range(24)]
        minutes = ['0'[len(str(minute)) - 1:] + str(minute) for minute in range(60)]
        return {'utilities': UTILITY_LIST, 'current_reader': current_reader, 'tzs': pytz.common_timezones, 'reminder_start': reminder_start, 'months': months, 'days': days, 'hours': hours, 'minutes': minutes, 'now': reminder_start}


class SendRead(MonadHandler):
    def http_get(self, inv):
        current_reader = Reader.require_current_reader()
        read_key = inv.get_string('read_key')
        read = Read.get_read(read_key)
        if current_reader.key() != read.meter.reader.key():
            raise ForbiddenException()
        return inv.send_ok(self.page_fields(current_reader, read))


    def http_post(self, inv):
        try:
            current_reader = Reader.require_current_reader()
            read_key = inv.get_string('read_key')
            read = Read.get_read(read_key)
            meter = read.meter
            if current_reader.key() != meter.reader.key():
                raise ForbiddenException()
            if inv.has_control('update'):
                meter.send_read_to = inv.get_string('send_read_to').strip()
                meter.send_read_name = inv.get_string('send_read_name').strip() 
                meter.send_read_reader_email = inv.get_string('send_read_reader_email').strip()
                meter.send_read_address = inv.get_string('send_read_address').strip()
                meter.send_read_postcode = inv.get_string('send_read_postcode').strip()
                meter.send_read_account = inv.get_string('send_read_account').strip()
                meter.send_read_msn = inv.get_string('send_read_msn').strip()
                meter.put()
                fields = self.page_fields(current_reader, read)
                fields['message'] = "Info updated successfully."
                return inv.send_ok(fields)
            else:
                if meter.send_read_to is None or len(meter.send_read_to) == 0:
                    raise UserException("The supplier's email address must be filled in.")
                body = django.template.Template("""Hi, I'd like to submit a reading for my {{ read.meter.utility_id }} meter. Details below:

My Name: {{ read.meter.send_read_name }} 
My Email Address: {{ read.meter.send_read_reader_email }} 
First Line Of Postal Address Of Meter: {{ read.meter.send_read_address }} 
Postcode Of Meter: {{ read.meter.send_read_postcode }}
Account Number: {{ read.meter.send_read_account }}
Meter Serial Number: {{ read.meter.send_read_msn }}
Read Date: {{ read.local_read_date|date:"Y-m-d H:i" }}
Reading: {{ read.value }} {{ read.meter.units }}""").render(django.template.Context({'read': read}))
                
                mail.send_mail(sender="MtrHub <mtrhub@mtrhub.com>", to=meter.send_read_to, cc=meter.send_read_reader_email,
                                reply_to=meter.send_read_reader_email, subject="My " + meter.utility_id + " meter reading",
                                body=body)

                meter.latest_customer_read_date = read.read_date
                meter.put()
                
                fields = self.page_fields(current_reader, read)
                fields['message'] = "Reading sent successfully."
                return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(current_reader, read)
            raise e
    
    def page_fields(self, current_reader, read):
        return {'read': read, 'current_reader': current_reader}


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
            
            if inv.has_control('delete'):
                fields = self.page_fields(meter, current_reader)
                meter.delete_meter()
                fields['message'] = 'Meter deleted successfully.'
                return inv.send_see_other('/')
            else:
                is_public = inv.has_control('is_public')
                email_address = inv.get_string('email_address')
                confirm_email_address = inv.get_string('confirm_email_address')
                reminder_frequency = inv.get_string('reminder_frequency')
                utility_units = inv.get_string('utility_units')
                name = inv.get_string('name')
                time_zone = inv.get_string('time_zone')
                reminder_start = inv.get_datetime("reminder_start", pytz.timezone(time_zone))

                utility_id, units = utility_units.split('-')
                email_address = email_address.strip()
                if email_address != confirm_email_address.strip():
                    raise UserException("The email addresses don't match")
                customer_read_frequency = inv.get_string('customer_read_frequency')
                meter.update(utility_id, units, name, time_zone, is_public, email_address, reminder_start, reminder_frequency, customer_read_frequency)
                fields = self.page_fields(meter, current_reader)
                fields['message'] = 'Settings updated successfully.'
                return inv.send_ok(fields)
        except UserException, e:
            e.values = self.page_fields(meter, current_reader)
            raise e

    def page_fields(self, meter, current_reader):
        if meter.reminder_start is None:
            reminder_start = datetime.datetime.now()
        else:
            reminder_start = meter.reminder_start
        reminder_start_datetime = reminder_start.replace(tzinfo=pytz.timezone('UTC')).astimezone(pytz.timezone(meter.time_zone))
        reminder_start = {'year': reminder_start_datetime.year, 'month': '0'[len(str(reminder_start.month)) - 1:] + str(reminder_start_datetime.month), 'day': '0'[len(str(reminder_start_datetime.day)) - 1:] + str(reminder_start_datetime.day), 'hour': '0'[len(str(reminder_start_datetime.hour)) - 1:] + str(reminder_start_datetime.hour), 'minute': '0'[len(str(reminder_start_datetime.minute)) - 1:] + str(reminder_start_datetime.minute)}
        days = ['0'[len(str(day)) - 1:] + str(day) for day in range(1,32)]
        months = ['0'[len(str(month)) - 1:] + str(month) for month in range(1,13)]
        hours = ['0'[len(str(hour)) - 1:] + str(hour) for hour in range(24)]
        minutes = ['0'[len(str(minute)) - 1:] + str(minute) for minute in range(60)]
        return {'utilities': UTILITY_LIST, 'current_reader': current_reader, 'meter': meter, 'tzs': pytz.common_timezones, 'reminder_start': reminder_start, 'months': months, 'days': days, 'hours': hours, 'minutes': minutes, 'now': reminder_start}


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

            if inv.has_control('remove_openid'):
                openid = inv.get_string('openid')
                if openid in reader.openids:
                    reader.openids.remove(openid)
                    reader.put()
                    fields = self.page_fields(reader)
                    fields['message'] = "Successfully removed OpenId."
                    return inv.send_ok(fields)
                else:
                    raise UserException("That OpenId isn't associated with the reader.")
                    
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
                    meter.delete_meter()
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
                    value = float(row[1].strip())
                    read = Read(meter=meter, read_date=read_date, value=value)
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
                rate = (read.value - first_read.value) / self.total_seconds(read.read_date - first_read.read_date)
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
        
        labels = ','.join('"' + datetime.datetime.strftime(month['start_date'], '%b %Y') + '"' for month in months)
        data = ','.join(str(round(month['kwh'], 2)) for month in months)
        return {'current_reader': Reader.get_current_reader(), 'meter': meter, 'data': data, 'labels': labels}


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

  
    def page_fields(self, current_reader, read):      
        days = [{'display': '0'[len(str(day)) - 1:] + str(day), 'number': day} for day in range(1,32)]        
        months = [{'display': '0'[len(str(month)) - 1:] + str(month), 'number': month} for month in range(1,13)]
        hours = [{'display': '0'[len(str(hour)) - 1:] + str(hour), 'number': hour} for hour in range(24)]
        minutes = [{'display': '0'[len(str(minute)) - 1:] + str(minute), 'number': minute} for minute in range(60)]

        return {'current_reader': current_reader, 'read': read, 'months': months, 'days': days, 'hours': hours, 'minutes': minutes}


class EditRead(MonadHandler):
    def http_get(self, inv):
        current_reader = Reader.require_current_reader()
        read_key = inv.get_string("read_key")
        read = Read.get_read(read_key)
        return inv.send_ok(self.page_fields(current_reader, read))
  
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
                value = inv.get_float("value")
                read.update(read_date, value)
                fields = self.page_fields(current_reader, read)
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