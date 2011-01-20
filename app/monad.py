import os
from google.appengine.api import users
from google.appengine.ext.webapp import template
from urllib import quote
import cgi
from wsgiref.headers import Headers
import urlparse
import datetime

class HttpException(Exception):
    def __init__(self, message=None):
        self.values = {}
        self.message = message

        
class MethodNotAllowedException(HttpException):
    pass


class UnauthorizedException(HttpException):
    pass


class InternalServerErrorException(HttpException):
    pass


class UserException(HttpException):
    pass


class NotFoundException(HttpException):
    pass


class ForbiddenException(HttpException):
    pass


class Invocation():
    content_types = {'html': 'text/html', 'atom': 'application/xhtml+xml', 'xrds': 'application/xrds+xml'}
    
    def __init__(self, environ, start_response, template_dir):
        self.path_info = environ['PATH_INFO']
        self.template_dir = template_dir
        self.environ = environ
        self.start_response = start_response
        self.controls = {}
        fields = cgi.FieldStorage()
        for key in fields.keys():
            self.controls[key] = unicode(fields[key].value, 'utf_8')
        self.header_list = []
        self.headers = Headers(self.header_list)


    def reconstruct_url(self):
        return self.home_url() + quote(self.environ.get('PATH_INFO',''))


    def _send(self, response, values=None):
        if values is None:
            self.start_response(response, self.header_list)
            return

        if not values.has_key('type'):
            values['type'] = 'html'
        type = values['type']
        if Invocation.content_types.has_key(type):
            self.headers.add_header('Content-Type', Invocation.content_types[type])
        else:
            raise UserException('Content type not recognized')
        values['controls'] = self.controls
        user = users.get_current_user()
        if user is not None:
            values['user'] = user
        self.start_response(response, self.header_list)
        if self.path_info == '/':
            template_name = "root." + type
        else:
            template_name = self.path_info[1:] + "." + type
        return [template.render(os.path.join(self.template_dir, template_name), values)]
    
    def home_url(self):
        url = self.environ['wsgi.url_scheme']+'://'
        if self.environ.get('HTTP_HOST'):
            url += self.environ['HTTP_HOST']
        else:
            url += self.environ['SERVER_NAME']
            if self.environ['wsgi.url_scheme'] == 'https':
                if self.environ['SERVER_PORT'] != '443':
                    url += ':' + self.environ['SERVER_PORT']
            else:
                if self.environ['SERVER_PORT'] != '80':
                    url += ':' + self.environ['SERVER_PORT']
        return url
    
    def send_ok(self, values):
        return self._send('200 OK', values)

    def send_moved_permanently(self, location):
        self.headers.add_header('Location', location)
        self._send('301 Moved Permanently')

    def send_see_other(self, url):
        if urlparse.urlparse(url).scheme == '':
            url = self.home_url() + url
        self.headers.add_header('Location', url)
        self._send('303 See Other')
    
    def send_method_not_allowed(self):
        self._send('405 Method Not Allowed')
        return ['405 Method Not Allowed']

    def send_forbidden(self):
        self._send('403 Forbidden')
        return ['403 Forbidden']
    
    def send_user_exception(self, values):
        return self._send('418 User Exception', values)

    def send_not_found(self, message=None):
        self._send('404 Not Found')
        if message is None:
            message = '404 Not Found'
        return [message]
    
    def has_control(self, name):
        return self.controls.has_key(name)
        
    def get_string(self, name):
        if self.has_control(name):
            return self.controls[name]
        else:
            raise UserException("The field '" + name + "' is needed.")
    
    def get_datetime(self, name):
        return datetime.datetime(*[self.get_integer(name + "-" + suffix) for suffix in ['year', 'month', 'day', 'hour', 'minute']])
    
    
    def get_integer(self, name):
        return int(self.get_string(name))
    
    
    def get_float(self, name):
        return float(self.get_string(name))


class MonadHandler(object):
    def http_get(self, inv):
        raise MethodNotAllowedException()
    
    def http_post(self, inv):
        raise MethodNotAllowedException()


class Monad(object):
    def __init__(self, handlers):
        self.handlers = handlers
        self.template_path = os.path.join(os.path.dirname(__file__), 'templates')

    def __call__(self, environ, start_response):
        inv = Invocation(environ, start_response, self.template_path)
        if inv.path_info not in self.handlers:
            return inv.send_not_found()
        urlable = self.handlers[inv.path_info]
        method = environ['REQUEST_METHOD']
        try:
            if method == 'GET':
                return urlable.http_get(inv)
            elif method == 'POST':
                return urlable.http_post(inv)
        except MethodNotAllowedException:
            return inv.send_method_not_allowed()
        except InternalServerErrorException:
            return inv.send_internal_server_error()
        except UserException, e:
            e.values['message'] = e.message
            return inv.send_user_exception(e.values)
        except NotFoundException, e:
            return inv.send_not_found(e.message)
        except ForbiddenException:
            return inv.send_forbidden()