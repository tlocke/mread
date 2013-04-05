from google.appengine.ext import db
from google.appengine.api import users, mail
import datetime
import csv
import dateutil.relativedelta
import dateutil.rrule
import pytz
import string
import random
import sys


UTILITY_DICT = {'electricity':
        {'id': 'electricity', 'name': 'Electricity', 'units': ['kWh']},
        'water': {'id': 'water', 'name': 'Water', 'units': ['m3']},
        'gas': {'id': 'gas', 'name': 'Gas', 'units': ['m3', 'ft3']}}

UTILITY_IDS = UTILITY_DICT.keys()

UTILITY_LIST = [val for val in UTILITY_DICT.values()]

class Configuration(db.Model):
    session_key = db.StringProperty(required=True)


class Reader(db.Model):
    name = db.StringProperty(required=True, default='Me')
    openids = db.StringListProperty(required=True)
    proposed_openid = db.StringProperty(required=False, default='')

    @staticmethod
    def find_current_reader():
        user = users.get_current_user()
        if user is None:
            return None
        else:
            return Reader.gql("where openids = :1",
                    str(user.federated_identity())).get()

    @staticmethod
    def get_reader(key):
        reader = Reader.get(key)
        if reader is None:
            raise UserException("Can't find a reader with key " + key)
        return reader


class UserException(Exception):
    pass


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
            raise UserException("The meter can't be found.")
        return meter

    def update(self, utility_id, units, name, tz_name, is_public,
            email_address, reminder_start, reminder_frequency,
            customer_read_frequency):
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
        naive_now = self.get_tzinfo().normalize(pytz.utc.localize(
                datetime.datetime.now()).astimezone(
                self.get_tzinfo())).replace(tzinfo=None)
        self.next_reminder = pytz.utc.normalize(self.get_tzinfo().localize(
                naive_rrule.after(naive_now)).astimezone(pytz.utc))

    def local_next_reminder(self):
        return self.get_tzinfo().normalize(pytz.utc.localize(
            self.next_reminder).astimezone(self.get_tzinfo()))

    def local_reminder_start(self):
        return self.get_tzinfo().normalize(pytz.utc.localize(
                self.reminder_start).astimezone(self.get_tzinfo()))

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

        return Read.gql("""where meter = :1 and read_date > :2 order by
                read_date desc""", self,
                cust_date +
                dateutil.relativedelta.relativedelta(months=months)).get()


class Read(db.Model):
    read_date = db.DateTimeProperty(required=True)
    meter = db.ReferenceProperty(Meter)
    value = db.FloatProperty(required=True)

    @staticmethod
    def get_read(key):
        read = Read.get(key)
        if read is None:
            raise UserException("Can't find the read with key " + str(key))
        return read

    def update(self, read_date, value):
        if read_date > datetime.datetime.now():
            raise UserException("The read date can't be in the future.")
        self.read_date = read_date
        self.value = value
        self.put()

    def local_read_date(self):
        return self.read_date.replace(tzinfo=pytz.timezone('UTC')).astimezone(
                pytz.timezone(self.meter.time_zone))
