[
    {
        'name': "Look at home page",
        'port': 8080,
        'host': 'localhost',
        'path': "/",
        'status_code': "200"},

    {
        'name': "Try logging in.",
        'path': '/_ah/login?email=test@example.com&'
        'action=Login&continue=http://localhost:8080/',
        'status_code': 302},

    {
        'name': 'Create account',
        'path': "/add_reader",
        'method': "post",
        'data': {
            "name": "Test"},
        'status_code': "303"},
    {
        'name': 'Check account creation message',
        'path': "/",
        'status_code': "200",
        'regexes': ["Account created successfully."]},

    {
        'name': "Add a meter",
        'path': "/add_meter",
        'method': "post",
        'tries': {},
        'data': {
            "utility_units": "electricity-kWh",
            "name": "House",
            "time_zone": "UTC",
            "email_address": "None",
            "confirm_email_address": "None",
            "reminder_frequency": "never",
            "reminder_start_year": "2011",
            "reminder_start_month": "05",
            "reminder_start_day": "01",
            "reminder_start_hour": "18",
            "reminder_start_minute": "30",
            "customer_read_frequency": "monthly"},
        'status_code': 303},

    {
        'name': "View the meter.",
        'path': "/view_meter?meter_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'regexes': [
            r'">Sign Out</a>',
            '>Test<'],
        'status_code': 200},

    {
        'name': "View meter settings.",
        'path': "/meter_settings?"
        "meter_key=ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'regexes': [
            '>Test<',
            '<option value="electricity-kWh" '
            'selected>Electricity - kWh</option>'],
        'status_code': 200},
    {
        'name': "Insert a read.",
        'path': "/view_meter",
        'method': "post",
        'data': {
            "meter_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
            "read_year": "2011",
            "read_month": "02",
            "read_day": "13",
            "read_hour": "17",
            "read_minute": "48",
            "value": "41"},
        'regexes': [
            r'<p>\s*'
            r'The <a '
            r'href="/view_read\?read_key=ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFk'
            r'GICAgICAgMAIDA">reading</a> has been\s*'
            r'successfully created.\s*</p>'],
        'status_code': 200},

    {
        'name': "View the read.",
        'path': "/view_read?read_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAIDA",
        'status_code': 200},

    {
        'name': "View the edit_read page.",
        'path': "/edit_read?read_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAIDA",
        'status_code': 200,
        'regexes': [
            '<legend>Delete This Read</legend>\s*<input '
            'type="hidden" name="read_key" '
            'value="ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAIDA"',

            r'<title>\s*'
            r'MtrHub &gt; Meter: House &gt;\s*'
            r'Read 2011-02-13 17:48\s*'
            r'</title>']},
    {
        'name': "Insert a read with a blank value.",
        'path': "/view_meter",
        'method': "post",
        'data': {
            "meter_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
            "read_year": "2011",
            "read_month": "02",
            "read_day": "13",
            "read_hour": "18",
            "read_minute": "48",
            "value": ""},
        'status_code': "400",
        'regexes': [
            "The 'value' field doesn't seem to be a number\."]},

    {
        'name': "Try inserting a read that's not a number.",
        'path': "/view_meter",
        'method': "post",
        'data': {
            "meter_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
            "read_year": "2011",
            "read_month": "02",
            "read_day": "13",
            "read_hour": "18",
            "read_minute": "48",
            "value": "sportive bombination"},
        'status_code': "400",
        'regexes': [
            "The 'value' field doesn't seem to be a number\."]},

    {
        'name': "Delete a read.",
        'path': "/edit_read",
        'method': "post",
        'data': {
            "read_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAIDA",
            "delete": "Delete"},
        'status_code': "303"},

    {
        'name': "Insert another read.",
        'path': "/view_meter",
        'method': "post",
        'data': {
            "meter_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
            "read_year": "2011",
            "read_month": "02",
            "read_day": "15",
            "read_hour": "18",
            "read_minute": "40",
            "value": "49"},
        'status_code': 200},

    {
        'name': "Have a look at the upload page.",
        'path': "/upload?meter_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'regexes': [
            r'"/view_meter\?meter_key='
            r'ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww"'],
        'status_code': "200"},

    {
        'name': "Have a look at the chart page.",
        'path': "/chart?meter_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'regexes': ['Sign Out'],
        'status_code': 200},

    {
        'name': "Have a look at the reader.",
        'path': "/view_reader?reader_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchMLEgZSZWFkZXIYgICAgICAgAkM",
        'regexes': 'Sign Out',
        'status_code': 200},

    {
        'name': "Propose an email.",
        'path': "/reader_settings",
        'method': "post",
        'data': {
            "reader_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchMLEgZ"
            "SZWFkZXIYgICAgICAgAkM",
            "proposed_email": "pink@example.com",
            "propose_email": "Propose Email"},
        'status_code': 200},

    {
        'name': "Try and view the meter without being signed in",
        'path': '/_ah/login?continue=http%3A//localhost%3A8080/&'
        'action=logout'},

    {
        'path': "/view_meter?meter_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'status_code': 401},

    {
        'name': "Try logging in.",
        'path': '/_ah/login?email=test@example.com&'
        'action=Login&continue=http://localhost:8080/',
        'status_code': 302},

    {
        'name': "Also change utility to gas, and reminder frequency to "
        "'monthly'",
        'path': "/meter_settings",
        'method': "post",
        'data': {
            "meter_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
            "utility_units": "gas-m3",
            "name": "House",
            "time_zone": "UTC",
            "email_address": "None",
            "confirm_email_address": "None",
            "reminder_frequency": "monthly",
            "reminder_start_year": "2011",
            "reminder_start_month": "05",
            "reminder_start_day": "01",
            "reminder_start_hour": "18",
            "reminder_start_minute": "30",
            "is_public": "True",
            "customer_read_frequency": "monthly"},
        'status_code': 200},

    {
        'name': "Try and view the meter without being signed in",
        'path': '/_ah/login?continue=http%3A//localhost%3A8080/&'
        'action=logout'},

    {
        'name': "Check the details of the public meter are shown",
        'path': "/",
        'regexes': [
            r'<ul>\s*<li>\s*<a\s*'
            r'title="Gas House meter at 2011-02-15 18:40"\s*'
            r'href="/view_read\?read_key=ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkG'
            r'ICAgICAgMAKDA">49.0\s*'
            r'm<sup>3</sup></a> by\s*'
            r'Test\s*'
            r'</li>']},

    {
        'path': "/view_read?read_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAKDA",
        'status_code': "200"},

    {
        'name': "Try admin stuff. Sign in as administrator",
        'path': "/_ah/login?email=admin@example.com&admin=True&"
        "continue=http://localhost:8080/&action=Login",
        'status_code': 302},

    {
        'name': "Try sending the reminders",
        'path': "/cron/reminders",
        'status_code': 200},

    {
        'name': "And Sign out the administrator",
        'path': "/_ah/login?continue=http%3A//localhost%3A8080/&action=Logout",
        'status_code': 302},

    {
        'name': "Try logging in.",
        'path': '/_ah/login?email=pink@example.com&'
        'action=Login&continue=http://localhost:8080/',
        'status_code': 302},

    {
        'path': "/welcome",
        'regexes': [
            'pink@example.com'],
        'status_code': "200"},

    {
        'path': "/welcome",
        'method': "post",
        'data': {
            "reader_key": "ahBkZXZ-"
            "bWV0ZXJlYWQtaHJkchMLEgZSZWFkZXIYgICAgICAgAkM",
            "associate": "Associate"},
        'status_code': "303"},

    {
        'name': "Check that 'gas' is still displayed",
        'path': "/meter_settings?meter_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'tries': {},
        'regexes': [
            '<option value="gas-m3" selected>Gas - '
            'm&sup3;</option>'],
        'status_code': "200"},

    {
        'name': "Try editing a read",
        'path': "/edit_read",
        'method': "post",
        'data': {
            "read_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAKDA",
            "read_year": "2011",
            "read_month": "07",
            "read_day": "21",
            "read_hour": "18",
            "read_minute": "40",
            "value": "49.0"},
        'status_code': 303},

    {
        'name': "Send a customer read. Set header data",
        'path': "/send_read",
        'method': "post",
        'data': {
            "read_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAKDA",
            "send_read_to": "supplier@example.com",
            "send_read_name": "Sun Tzu",
            "send_read_reader_email": "stzu@example.com",
            "send_read_address": "21b Baker Street",
            "send_read_postcode": "78560992",
            "send_read_account": "89u5u809",
            "send_read_msn": "sdjii388",
            "update": "Update"},
        'status_code': 200},

    {
        'path': "/send_read",
        'method': "post",
        'data': {
            "read_key": "ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAKDA",
            "send": "Send"},
        'status_code': 200},

    {
        'path': "/view_meter?meter_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'regexes': [
            "<th>Date of last customer read</th>",
            "<td>\s*2011-07-21 18:40\s*</td>"],
        'status_code': 200},

    {
        'name': "Export reads",
        'path': "/export_reads?meter_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'status_code': "200"}]
