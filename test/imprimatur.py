[
    {
        'name': "Look at home page",
        'port': 8080,
        'host': 'localhost',
        'path': "/",
        'status_code': "200"},

    {
        'name': "Try logging in.",
        'path': "/xhr/sign_in",
        'method': "post",
        'data': {
            "assert": "assrt",
            "user_email": "test@example.com"},
        'status_code': "200"},

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
            '&lt;a id="signout" '
            'href="javascript:void\(0\)"&gt;Sign Out&lt;/a&gt;',
            '&gt;Test&lt;'],
        'status_code': 200},

    {
        'name': "View meter settings.",
        'path': "/meter_settings?"
        "meter_key=ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'regexes': [
            '&gt;Test&lt;',
            '&lt;option value="electricity-kWh" '
            'selected&gt;Electricity - kWh&lt;/option&gt;'],
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
            '&lt;legend&gt;Delete This Read&lt;/legend&gt;\s*&lt;input '
            'type="hidden" name="read_key" '
            'value="ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAIDA"']},
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
        'regexes': '"/view_meter\?meter_key='
        'ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww"',
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
        'path': "/xhr/sign_out"},

    {
        'path': "/view_meter?meter_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'status_code': 401},

    {
        'name': "Log in, change the meter to public and check it's there on "
        "the homepage.",
        'path': "/xhr/sign_in",
        'method': "post",
        'data': {
            "assert": "assrt",
            "user_email": "test@example.com"},
        'status_code': 200},

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
        'path': "/xhr/sign_out",
        'status_code': 200},

    {
        'name': "Check the details of the public meter is shown",
        'path': "/",
        'regexes': [
            '&lt;tr&gt;\s*&lt;td&gt;Test&lt;/td&gt;\s*&lt;td&gt;\s*'
            '&lt;a href="/view_meter\?meter_key='
            'ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww"&gt;'
            'House&lt;/a&gt;\s*&lt;/td&gt;\s*&lt;td&gt;Gas&lt;/td&gt;\s*'
            '&lt;td&gt;2011-02-15 18:40&lt;/td&gt;\s*&lt;td&gt;\s*'
            '&lt;a href="/view_read\?read_key='
            'ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAKDA"'
            '&gt;49\.0&lt;/a&gt;\s*&lt;/td&gt;\s*'
            '&lt;td&gt;m&lt;sup&gt;3&lt;/sup&gt;\s*&lt;/td&gt;']},

    {
        'path': "/view_read?read_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchELEgRSZWFkGICAgICAgMAKDA",
        'status_code': "200"},

    {
        'name': "Try admin stuff. Sign in as administrator",
        'path': "/_ah/login?email=admin@example.com&amp;admin=True&"
        "amp;continue=http://localhost:8080/&amp;action=Login",
        'status_code': 200},

    {
        'name': "Try sending the reminders",
        'path': "/cron/reminders",
        'status_code': "200"},

    {
        'name': "And Sign out the administrator",
        'path': "/_ah/login?continue=http%3A//localhost%3A8080/&action=Logout",
        'status_code': "200"},

    {
        'name': "Log in with proposed email",
        'path': "/xhr/sign_in",
        'method': "post",
        'data': {
            "assert": "assrt",
            "user_email": "pink@example.com"},
        'status_code': "200"},
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
            '&lt;option value="gas-m3" selected&gt;Gas - '
            'm&amp;sup3;&lt;/option&gt;'],
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
        'status_code': 200},

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
        'regex': [
            "&lt;th&gt;Date of last customer read&lt;/th&gt;",
            "&lt;td&gt;\s*2011-07-21 18:40\s*&lt;/td&gt;"],
        'status_code': 200},

    {
        'name': "Export reads",
        'path': "/export_reads?meter_key="
        "ahBkZXZ-bWV0ZXJlYWQtaHJkchILEgVNZXRlchiAgICAgICACww",
        'status_code': "200"}]
