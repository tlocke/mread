import jinja2
import webapp2
from google.appengine.api import users, mail
import datetime
import csv
import dateutil.relativedelta
import dateutil.rrule
import pytz
import string
import random
from webapp2_extras import sessions
from models import (
    Meter, Read, UserException, Reader, UTILITY_LIST, Configuration,
    get_federated_identity)


jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader('templates'))

MIME_MAP = {'html': 'text/html', 'atom': 'application/atom+xml'}


class MReadHandler(webapp2.RequestHandler):
    def dispatch(self):
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)
        self.session = self.session_store.get_session()

        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    def add_flash(self, message):
        self.session.add_flash(message)

    def return_template(self, status, template_values):
        user = users.get_current_user()
        if user is not None:
            template_values['user'] = user
            template_values['signout_url'] = users.create_logout_url('/')
            reader = Reader.find_current_reader()
            if reader is not None:
                template_values['current_reader'] = reader
        self.response.status = status

        try:
            template_name = template_values['template_name']
        except KeyError:
            template_name = template_names[self.__class__.__name__]
        flashes = [flash[0] for flash in self.session.get_flashes()]
        mime_type = MIME_MAP[template_name.split('.')[-1]]
        self.response.headers['Content-Type'] = mime_type
        template = jinja_environment.get_template(template_name)
        self.response.out.write(
            template.render(
                request=self.request, flashes=flashes, **template_values))

    def send_ok(self, template_values):
        self.return_template('200 OK', template_values)

    def send_found(self, location):
        self.redirect(location, 302)

    def send_bad_request(self, template_values):
        self.return_template('400 BAD REQUEST', template_values)

    def return_unauthorized(self):
        self.abort(401)

    def send_forbidden(self):
        self.abort(403)

    def send_see_other(self, location):
        self.redirect(location, code=303)

    def get_str(self, name):
        try:
            return self.request.GET[name]
        except KeyError:
            raise UserException("The field " + name + " is needed.")

    def post_str(self, name):
        try:
            return self.request.POST[name]
        except KeyError:
            raise UserException("The field " + name + " is needed.")

    def post_datetime(self, prefix, tzinfo=None):
        try:
            year = self.post_int(prefix + "_year")
            month = self.post_int(prefix + "_month")
            day = self.post_int(prefix + "_day")
            hour = self.post_int(prefix + "_hour")
            minute = self.post_int(prefix + "_minute")
            if tzinfo is None:
                return datetime.datetime(year, month, day, hour, minute)
            else:
                local_dt = tzinfo.localize(
                    datetime.datetime(year, month, day, hour, minute))
                return pytz.utc.normalize(
                    local_dt.astimezone(pytz.utc)).replace(tzinfo=None)
        except ValueError, e:
            raise UserException(str(e))

    def post_int(self, name):
        return int(self.post_str(name))

    def post_float(self, name):
        try:
            return float(self.post_str(name))
        except ValueError:
            raise UserException(
                "The '" + name + "' field doesn't seem to be a number.")

    def require_current_reader(self):
        reader = Reader.find_current_reader()

        if reader is None:
            self.return_unauthorized()
        else:
            return reader


class ViewReader(MReadHandler):
    def get(self):
        reader_key = self.get_str('reader_key')
        reader = Reader.get_reader(reader_key)
        current_reader = self.require_current_reader()
        if current_reader.key() != reader.key():
            self.send_forbidden()

        self.send_ok(
            {
                'reader': reader,
                'meters': Meter.gql(
                    "where reader = :1", current_reader).fetch(10)})


FREQS = {'monthly': dateutil.rrule.MONTHLY, 'weekly': dateutil.rrule.WEEKLY}


class Home(MReadHandler):
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

    def get(self):
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
            current_reader = Reader.find_current_reader()
            if current_reader is not None:
                reader_meters = Meter.gql(
                    "where reader = :1", current_reader).fetch(10)
                fields['meters'] = reader_meters
                fields['candidate_customer_reads'] = [
                    cand for cand in [
                        meter.candidate_customer_read() for meter in
                        reader_meters] if cand is not None]
        self.send_ok(fields)


class SignIn(MReadHandler):
    def get(self):
        if users.get_current_user() is None:
            if 'free_openid' in self.request.GET:
                try:
                    openid = self.get_str('openid_identifier')
                except UserException as e:
                    e.values = self.page_fields()
                    raise e

                self.send_found(
                    users.create_login_url(
                        dest_url="/welcome", federated_identity=openid))
            else:
                self.send_ok(self.page_fields())
        else:
            self.send_found('/welcome')

    def page_fields(self):
        fields = {'providers': []}
        for url, name, img_name in [
                ('https://www.google.com/accounts/o8/id', 'Google', 'google'),
                ('yahoo.com', 'Yahoo', 'yahoo'),
                ('myspace.com', 'MySpace', 'myspace'),
                ('aol.com', 'AOL', 'aol'),
                ('myopenid.com', 'MyOpenID', 'myopenid')]:
            fields['providers'].append(
                {
                    'name': name,
                    'url': users.create_login_url(
                        dest_url="/welcome", federated_identity=url),
                    'img_name': img_name})
        return fields


class Welcome(MReadHandler):
    def get(self):
        user = users.get_current_user()
        if user is None:
            self.send_ok(self.page_fields(None))
        else:
            current_reader = Reader.find_current_reader()
            if current_reader is None:
                fields = self.page_fields(None)
                proposed_readers = Reader.gql(
                    "where proposed_openid = :1",
                    get_federated_identity(user)).fetch(10)
                if len(proposed_readers) > 0:
                    fields['proposed_readers'] = proposed_readers
                self.send_ok(fields)
            else:
                self.send_found('/')

    def post(self):
        user = users.get_current_user()
        if user is None:
            self.return_unauthorized()

        fi = get_federated_identity(user)
        if 'associate' in self.request.POST:
            current_reader = Reader.find_current_reader()
            if current_reader is None:
                reader_key = self.post_str('reader_key')
                reader = Reader.get_reader(reader_key)
                if reader.proposed_openid == fi:
                    reader.proposed_openid = ''
                    reader.openids.append(fi)
                    reader.put()
                    self.add_flash(
                        'The OpenId ' + fi + " has been successfully "
                        "associated with this reader.")
                    self.send_see_other(
                        '/view_reader?reader_key=' + str(reader.key()))
                else:
                    self.send_ok(
                        message="Can't associate " + fi +
                        " with the account " + reader.name +
                        " because the OpenId you're signed in with "
                        "doesn't match the proposed OpenId.")
            else:
                self.send_bad_request(
                    message="The OpenId " + fi +
                    " is already associated with an account.")
        else:
            current_reader = Reader.find_current_reader()
            if current_reader is None:
                current_reader = Reader(openids=[fi], name=user.nickname())
                current_reader.put()
                self.add_flash("Account created successfully.")

            self.send_see_other('/')

    def page_fields(self, current_reader):
        meters = Meter.gql("where reader = :1", current_reader).fetch(10)
        return {'meters': meters}


class ViewMeter(MReadHandler):
    def get(self):
        meter_key = self.get_str("meter_key")
        meter = Meter.get_meter(meter_key)
        if meter.is_public:
            current_reader = Reader.find_current_reader()
        else:
            current_reader = self.require_current_reader()
            if current_reader.key() != meter.reader.key():
                self.return_forbidden()
        self.send_ok(self.page_fields(meter, current_reader))

    def post(self):
        current_reader = self.require_current_reader()
        meter_key = self.post_str("meter_key")
        meter = Meter.get_meter(meter_key)
        if current_reader.key() != meter.reader.key():
            self.return_forbidden()

        try:
            read_date = self.post_datetime("read", meter.get_tzinfo())
            value = self.post_float("value")
            read = Read(meter=meter, read_date=read_date, value=value)
            read.put()
            fields = self.page_fields(meter, current_reader)
            fields['read'] = read.key()
            self.send_ok(fields)
        except UserException as e:
            self.send_bad_request(self.page_fields(meter, current_reader, e))

    def page_fields(self, meter, current_reader, message=None):
        reads = Read.gql(
            "where meter = :1 order by read_date desc", meter).fetch(30)
        now = meter.get_tzinfo().localize(datetime.datetime.now())

        return {'meter': meter, 'reads': reads, 'now': now,
                'candidate_customer_read': meter.candidate_customer_read(),
                'message': message}


class AddMeter(MReadHandler):
    def get(self):
        current_reader = self.require_current_reader()
        self.send_ok(self.page_fields(current_reader))

    def post(self):
        try:
            current_reader = self.require_current_reader()
            is_public = 'is_public' in self.request.POST
            reminder_frequency = self.post_str('reminder_frequency')
            name = self.post_str('name')
            time_zone = self.post_str('time_zone')
            reminder_start = self.post_datetime(
                "reminder_start", pytz.timezone(time_zone))
            utility_units = self.post_str('utility_units')
            if reminder_frequency == 'never':
                email_address = None
            else:
                email_address = self.post_str('email_address')
                confirm_email_address = self.post_str('confirm_email_address')
                email_address = email_address.strip()
                if email_address != confirm_email_address.strip():
                    raise UserException("The email addresses don't match.")
            customer_read_frequency = self.post_str('customer_read_frequency')

            meter = Meter(
                reader=current_reader, email_address=email_address,
                reminder_start=reminder_start,
                reminder_frequency=reminder_frequency,
                is_public=is_public, name=name, time_zone=time_zone,
                customer_read_frequency=customer_read_frequency)
            meter.put()
            utility_id, units = utility_units.split('-')
            meter.update(
                utility_id, units, name, time_zone, is_public, email_address,
                reminder_start, reminder_frequency, customer_read_frequency)
            fields = self.page_fields(current_reader)
            fields['location'] = '/meter?meter_key=' + str(meter.key())
            self.send_ok(fields)
        except UserException as e:
            self.send_bad_request(self.page_fields(current_reader, e))

    def page_fields(self, current_reader, message=None):
        reminder_start = datetime.datetime.now()
        reminder_start = {
            'year': reminder_start.year,
            'month': '0'[len(str(reminder_start.month)) - 1:] +
            str(reminder_start.month),
            'day': '0'[len(str(reminder_start.day)) - 1:] +
            str(reminder_start.day),
            'hour': '0'[len(str(reminder_start.hour)) - 1:] +
            str(reminder_start.hour),
            'minute': '0'[len(str(reminder_start.minute)) - 1:] +
            str(reminder_start.minute)}
        days = ['0'[len(str(day)) - 1:] + str(day) for day in range(1, 32)]
        months = [
            '0'[len(str(month)) - 1:] + str(month) for month in range(1, 13)]
        hours = ['0'[len(str(hour)) - 1:] + str(hour) for hour in range(24)]
        minutes = [
            '0'[len(str(minute)) - 1:] + str(minute) for minute in range(60)]
        return {'utilities': UTILITY_LIST, 'current_reader': current_reader,
                'tzs': pytz.common_timezones, 'reminder_start': reminder_start,
                'months': months, 'days': days, 'hours': hours,
                'minutes': minutes, 'now': reminder_start,
                'message': message}


class SendRead(MReadHandler):
    def get(self):
        current_reader = Reader.require_current_reader()
        read_key = self.get_str('read_key')
        read = Read.get_read(read_key)
        if current_reader.key() != read.meter.reader.key():
            self.return_forbidden()
        self.send_ok(self.page_fields(current_reader, read))

    def post(self):
        try:
            current_reader = self.require_current_reader()
            read_key = self.post_str('read_key')
            read = Read.get_read(read_key)
            meter = read.meter
            if current_reader.key() != meter.reader.key():
                self.return_forbidden()
            if 'update' in self.request.POST:
                meter.send_read_to = self.post_str('send_read_to').strip()
                meter.send_read_name = self.post_str('send_read_name').strip()
                meter.send_read_reader_email = self.post_str(
                    'send_read_reader_email').strip()
                meter.send_read_address = self.post_str(
                    'send_read_address').strip()
                meter.send_read_postcode = self.post_str(
                    'send_read_postcode').strip()
                meter.send_read_account = self.post_str(
                    'send_read_account').strip()
                meter.send_read_msn = self.post_str('send_read_msn').strip()
                meter.put()
                fields = self.page_fields(current_reader, read)
                fields['message'] = "Info updated successfully."
                self.send_ok(fields)
            else:
                if meter.send_read_to is None or len(meter.send_read_to) == 0:
                    raise UserException("""The supplier's email address must be
                            filled in.""")
                body = jinja2.Template("""Hi, I'd like to submit a \
reading for my {{ read.meter.utility_id }} meter. Details below:

My Name: {{ read.meter.send_read_name }}
My Email Address: {{ read.meter.send_read_reader_email }}
First Line Of Postal Address Of Meter: {{ read.meter.send_read_address }}
Postcode Of Meter: {{ read.meter.send_read_postcode }}
Account Number: {{ read.meter.send_read_account }}
Meter Serial Number: {{ read.meter.send_read_msn }}
Read Date: {{ read.local_read_date().strftime("%Y-%m-%d %H:%M") }}
Reading: {{ read.value }} {{ read.meter.units }}""").render(read=read)

                mail.send_mail(
                    sender="MtrHub <mtrhub@mtrhub.com>",
                    to=meter.send_read_to, cc=meter.send_read_reader_email,
                    reply_to=meter.send_read_reader_email,
                    subject="My " + meter.utility_id + " meter reading",
                    body=body)

                meter.latest_customer_read_date = read.read_date
                meter.put()

                fields = self.page_fields(current_reader, read)
                fields['message'] = "Reading sent successfully."
                self.send_ok(fields)
        except UserException as e:
            e.values = self.page_fields(current_reader, read)
            raise e

    def page_fields(self, current_reader, read):
        return {'read': read, 'current_reader': current_reader}


class ExportReads(MReadHandler):
    def get(self):
        meter_key = self.get_str("meter_key")
        meter = Meter.get_meter(meter_key)
        if meter.is_public:
            current_reader = Reader.get_current_reader()
        else:
            current_reader = Reader.require_current_reader()
            if current_reader.key() != meter.reader.key():
                self.return_forbidden()

        reads = Read.gql(
            "where meter = :1 order by read_date desc", meter).fetch(1000)
        self.send_ok(
            {
                'reads': reads,
                'template-name': 'export_reads.csv',
                'content-type': 'text/csv',
                'content-disposition': 'attachment; filename=reads.csv;'})


class MeterSettings(MReadHandler):
    def get(self):
        meter_key = self.get_str("meter_key")
        meter = Meter.get_meter(meter_key)
        reader = self.require_current_reader()
        if reader.key() != meter.reader.key():
            self.return_forbidden()
        self.send_ok(self.page_fields(meter, reader))

    def post(self):
        current_reader = self.require_current_reader()
        meter_key = self.post_str("meter_key")
        meter = Meter.get_meter(meter_key)
        try:
            if current_reader.key() != meter.reader.key():
                self.return_forbidden()

            if 'delete' in self.request.POST:
                fields = self.page_fields(meter, current_reader)
                meter.delete_meter()
                fields['message'] = 'Meter deleted successfully.'
                self.send_see_other('/')
            else:
                is_public = 'is_public' in self.request.POST
                email_address = self.post_str('email_address')
                confirm_email_address = self.post_str('confirm_email_address')
                reminder_frequency = self.post_str('reminder_frequency')
                utility_units = self.post_str('utility_units')
                name = self.post_str('name')
                time_zone = self.post_str('time_zone')
                reminder_start = self.post_datetime(
                    "reminder_start", pytz.timezone(time_zone))

                utility_id, units = utility_units.split('-')
                email_address = email_address.strip()
                if email_address != confirm_email_address.strip():
                    raise UserException("The email addresses don't match")
                customer_read_frequency = self.post_str(
                    'customer_read_frequency')
                meter.update(
                    utility_id, units, name, time_zone, is_public,
                    email_address, reminder_start, reminder_frequency,
                    customer_read_frequency)
                fields = self.page_fields(meter, current_reader)
                fields['message'] = 'Settings updated successfully.'
                self.send_ok(fields)
        except UserException as e:
            self.send_bad_request(
                self.page_fields(meter, current_reader, str(e)))

    def page_fields(self, meter, current_reader, message=None):
        if message is None:
            messages = []
        else:
            messages = [message]
        if meter.reminder_start is None:
            reminder_start = datetime.datetime.now()
        else:
            reminder_start = meter.reminder_start
        reminder_start = reminder_start.replace(
            tzinfo=pytz.timezone(
                'UTC')).astimezone(pytz.timezone(meter.time_zone))
        return {'utilities': UTILITY_LIST, 'current_reader': current_reader,
                'meter': meter, 'tzs': pytz.common_timezones,
                'reminder_start': reminder_start, 'messages': messages}


class ReaderSettings(MReadHandler):
    def get(self):
        reader_key = self.get_str("reader_key")
        reader = Reader.get_reader(reader_key)
        current_reader = Reader.require_current_reader()
        if current_reader.key() != reader.key():
            self.return_forbidden()
        self.send_ok(self.page_fields(reader))

    def post(self):
        try:
            current_reader = self.require_current_reader()
            reader_key = self.post_str("reader_key")
            reader = Reader.get_reader(reader_key)
            if current_reader.key() != reader.key():
                self.return_forbidden()

            if 'remove_openid' in self.request.POST:
                openid = self.get_str('openid')
                if openid in reader.openids:
                    reader.openids.remove(openid)
                    reader.put()
                    fields = self.page_fields(reader)
                    fields['message'] = "Successfully removed OpenId."
                    self.send_ok(fields)
                else:
                    raise UserException("""That OpenId isn't associated with
                            the reader.""")

            elif 'propose_openid' in self.request.POST:
                proposed_openid = self.post_str('proposed_openid')
                reader.proposed_openid = proposed_openid.strip()
                reader.put()
                if len(proposed_openid) == 0:
                    message = "Proposed OpenId successfully set to blank."
                else:
                    message = """Proposed OpenId set successfully. Now sign out
                            and then sign in using the proposed OpenId"""
                self.send_ok(self.page_fields(reader, message))
            elif 'delete' in self.request.POST:
                for meter in Meter.gql("where reader = :1", reader):
                    meter.delete_meter()
                reader.delete()
                self.send_found('/welcome')
            else:
                name = self.post_str('name')
                reader.name = name
                reader.put()
                self.add_flash('Settings updated successfully.')
                self.send_see_other(
                    '/view_reader?reader_key=' + str(reader.key()))
        except UserException as e:
            self.send_bad_request(self.page_fields(reader, str(e)))

    def page_fields(self, reader, message=None):
        return {'reader': reader, 'current_reader': reader,
                'messages': [] if message is None else [message]}


class Upload(MReadHandler):
    def get(self):
        meter_key = self.get_str('meter_key')
        meter = Meter.get_meter(meter_key)
        current_reader = self.require_current_reader()
        if current_reader.key() != meter.reader.key():
            self.return_forbidden()

        self.send_ok(self.page_fields(meter, current_reader))

    def post(self):
        try:
            current_reader = Reader.require_current_reader()
            meter_key = self.post_str("meter_key")
            meter = Meter.get_meter(meter_key)
            if current_reader.key() != meter.reader.key():
                self.return_forbidden()

            file_item = self.post_file("spreadsheet")
            if file_item.filename.endswith(".csv"):
                rdr = csv.reader(file_item.file)
                for row in rdr:
                    if len(row) < 2:
                        raise UserException("""Expecting 2 fields per row, the
                                date in the format yyyy-MM-dd HH:mm followed by
                                the reading.""")
                    try:
                        read_date = datetime.datetime.strptime(
                            row[0].strip(), '%Y-%m-%d %H:%M')
                    except ValueError as e:
                        raise UserException(
                            "Problem at line number " + str(rdr.line_num) +
                            " of the file. The first field (the read date "
                            "field) isn't formatted correctly, it should be "
                            "of the form 2010-02-23T21:46. " + str(e))
                    value = float(row[1].strip())
                    read = Read(meter=meter, read_date=read_date, value=value)
                    read.put()
                fields = self.page_fields(meter, current_reader)
                fields['message'] = 'File imported successfully.'
                self.send_ok(fields)
            else:
                raise UserException("The file name must end with '.csv.'")
        except UserException as e:
            e.values = self.page_fields(meter, current_reader)
            raise e

    def page_fields(self, meter, current_reader):
        return {'current_reader': current_reader, 'meter': meter}


class Chart(MReadHandler):
    def get(self):
        self.send_ok(self.page_fields())

    def kwh(self, meter, start_date, finish_date):
        sum_kwh = 0
        code = 'complete-data'
        first_read = Read.gql("""where meter = :1 and read_date <= :2 order by
                read_date desc""", meter, start_date).get()
        if first_read is None:
            code = 'partial-data'
        last_read = Read.gql("""where meter = :1 and read_date >= :2 order by
                read_date""", meter, finish_date).get()
        if last_read is None:
            code = 'partial-data'
            q_finish = finish_date
        else:
            q_finish = last_read.read_date
        for read in Read.gql(
                "where meter = :1 and read_date > :2 and read_date <= :3 "
                "order by read_date", meter, start_date, q_finish):
            if first_read is not None:
                rate = (read.value - first_read.value) / \
                    self.total_seconds(read.read_date - first_read.read_date)
                sum_kwh += rate * max(
                    self.total_seconds(
                        min(read.read_date, finish_date)
                        - max(first_read.read_date, start_date)), 0)
            first_read = read
        return {'kwh': sum_kwh, 'code': code, 'start_date': start_date,
                'finish_date': finish_date}

    def total_seconds(self, td):
        return (td.microseconds + (td.seconds + td.days * 24 * 3600)
                * 10 ** 6) / 10 ** 6

    def page_fields(self):
        meter_key = self.get_str("meter_key")
        meter = Meter.get_meter(meter_key)
        now = datetime.datetime.now().date()
        now = datetime.datetime(now.year, now.month, 1)
        months = []
        for month in range(-11, 1):
            month_start = now + \
                dateutil.relativedelta.relativedelta(months=month)
            month_finish = month_start + \
                dateutil.relativedelta.relativedelta(months=1)

            months.append(self.kwh(meter, month_start, month_finish))

        labels = ','.join(
            '"' + datetime.datetime.strftime(month['start_date'], '%b %Y') +
            '"' for month in months)
        data = ','.join(str(round(month['kwh'], 2)) for month in months)
        return {'current_reader': Reader.find_current_reader(),
                'meter': meter, 'data': data, 'labels': labels}


class ViewRead(MReadHandler):
    def get(self):
        current_reader = Reader.find_current_reader()
        read_key = self.get_str("read_key")
        read = Read.get_read(read_key)
        meter = read.meter
        if meter.is_public:
            self.send_ok(self.page_fields(current_reader, read))
        elif current_reader is None:
            self.return_unauthorized()
        elif current_reader.key() == meter.reader.key():
            self.send_ok(self.page_fields(current_reader, read))
        else:
            self.return_forbidden()

    def page_fields(self, current_reader, read):
        return {'read': read, 'current_reader': current_reader}


class EditRead(MReadHandler):
    def get(self):
        current_reader = self.require_current_reader()
        read_key = self.get_str("read_key")
        read = Read.get_read(read_key)
        self.send_ok(self.page_fields(current_reader, read))

    def post(self):
        current_reader = self.require_current_reader()
        read_key = self.post_str("read_key")
        read = Read.get_read(read_key)
        try:
            meter = read.meter
            if current_reader.key() != meter.reader.key():
                self.return_forbidden()

            if 'delete' in self.request.POST:
                read.delete()
                self.send_see_other(
                    "/view_meter?meter_key=" + str(meter.key()))
            else:
                read_date = self.post_datetime("read")
                value = self.post_float("value")
                read.update(read_date, value)
                fields = self.page_fields(current_reader, read)
                fields['message'] = 'Read edited successfully.'
                self.send_ok(fields)
        except UserException as e:
            self.send_bad_request(self.page_fields(current_reader, read, e))

    def page_fields(self, current_reader, read, message=None):
        days = [
            {
                'display': '0'[len(str(day)) - 1:] + str(day),
                'number': day} for day in range(1, 32)]
        months = [
            {
                'display': '0'[len(str(month)) - 1:] + str(month),
                'number': month} for month in range(1, 13)]
        hours = [
            {
                'display': '0'[len(str(hour)) - 1:] + str(hour),
                'number': hour} for hour in range(24)]
        minutes = [
            {
                'display': '0'[len(str(minute)) - 1:] + str(minute),
                'number': minute} for minute in range(60)]

        return {'current_reader': current_reader, 'read': read,
                'months': months, 'days': days, 'hours': hours,
                'minutes': minutes, 'message': message}


class Cron(MReadHandler):
    def page_fields(self):
        return {}

    def get(self):
        self.send_ok(self.page_fields())


class Reminders(MReadHandler):
    def get(self):
        now = datetime.datetime.now()
        for meter in Meter.gql("""where next_reminder != null and
                next_reminder <= :1""", now):
            body = jinja2.Template("""
Hi,

This is a reminder from MtrHub to read your {{ meter.utility.id }} meter \
{{ meter.name }}. To change the settings, log in to:

http://www.mtrhub.com/

Regards,

MtrHub.
""").render(meter=meter)
            mail.send_mail(
                sender="MtrHub <mtrhub@mtrhub.com>",
                to=meter.email_address,
                subject="MtrHub: Remember to take a meter reading.",
                body=body)
            meter.set_next_reminder()
            meter.put()
        self.send_ok({})

routes = [
    (r'/', Home), (r'/sign_in', SignIn), (r'/view_meter', ViewMeter),
    (r'/view_read', ViewRead), (r'/edit_read', EditRead),
    (r'/send_read', SendRead), (r'/upload', Upload), (r'/chart', Chart),
    (r'/meter_settings', MeterSettings), (r'/view_reader', ViewReader),
    (r'/reader_settings', ReaderSettings), (r'/welcome', Welcome),
    (r'/export_reads', ExportReads), (r'/add_meter', AddMeter),
    (r'/cron', Cron), (r'/cron/reminders', Reminders)]
template_names = dict(
    [(cls.__name__, rt[1:] + '.html') for rt, cls in routes if rt != '/'])
template_names['Home'] = 'home.html'
conf = Configuration.all().get()
if conf is None:
    session_key = ''.join(
        random.choice(
            string.ascii_uppercase + string.digits) for x in range(10)
        ).encode('ascii', 'ignore')
    conf = Configuration(session_key=session_key)
    conf.put()
config = {
    'webapp2_extras.sessions': {
        'secret_key': conf.session_key.encode('ascii', 'ignore')}}
app = webapp2.WSGIApplication(routes, debug=True, config=config)
