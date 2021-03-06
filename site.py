#!/usr/bin/env python
#
# Copyright 2009 Facebook
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

import logging
import tornado.auth
import tornado.escape
import tornado.httpserver
import tornado.ioloop
import tornado.options
import tornado.web
import os.path
import time
import uuid

from tornado.options import define, options

# Conditionally enable HBase
hbase_enabled = False
if hbase_enabled: from pyhbase.connection import HBaseConnection

class Application(tornado.web.Application):
    def __init__(self):
        handlers = [
            (r"/", MainHandler),
            (r"/auth/login", AuthLoginHandler),
            (r"/auth/logout", AuthLogoutHandler),
            (r"/a/message/new", MessageNewHandler),
            (r"/a/message/updates", MessageUpdatesHandler),
        ]
        settings = dict(
            login_url="/auth/login",
            template_path=os.path.join(os.path.dirname(__file__), "templates"),
            static_path=os.path.join(os.path.dirname(__file__), "static"),
        )
        tornado.web.Application.__init__(self, handlers, **settings)


class BaseHandler(tornado.web.RequestHandler):
    def get_current_user(self):
        return self.get_cookie("user")


class MainHandler(BaseHandler):
    @tornado.web.authenticated
    def get(self):
        self.render("index.html", messages=MessageMixin.cache)


class MessageMixin(object):
    waiters = []
    cache = []
    cache_size = 200

    # Read initial cache from HBase
    if hbase_enabled:
        hbase_conn = HBaseConnection('localhost', 9090)    
        old_messages = hbase_conn.scan('message_log', cache_size)
        for message in old_messages:
            cache_entry = dict([(entry[u'qualifier'], entry[u'value'])
                                for entry in message[u'entries']])
            cache.insert(0, cache_entry)

    # TODO(hammer): Don't create a new connection every time
    # TODO(hammer): Would be handy to have MultiPut here
    @staticmethod
    def record_messages(messages):
        hbase_conn = HBaseConnection('localhost', 9090)
        for message in messages:
            hbase_conn.put('message_log', str(99999999999 - int(message["timestamp"])),
                           'messages:id', str(message["id"]),
                           'messages:from', str(message["from"]),
                           'messages:body', str(message["body"]),
                           'messages:html', str(message["html"]))

    def wait_for_messages(self, callback, cursor=None):
        cls = MessageMixin
        if cursor:
            index = 0
            for i in xrange(len(cls.cache)):
                index = len(cls.cache) - i - 1
                if cls.cache[index]["id"] == cursor: break
            recent = cls.cache[index + 1:]
            if recent:
                callback(recent)
                return
        cls.waiters.append(callback)

    def new_messages(self, messages):
        cls = MessageMixin
        logging.info("Sending new message to %r listeners", len(cls.waiters))
        for callback in cls.waiters:
            try:
                callback(messages)
            except:
                logging.error("Error in waiter callback", exc_info=True)
        cls.waiters = []
        cls.cache.extend(messages)

        # add to HBase
        if hbase_enabled: cls.record_messages(messages)

        # Expire messages off the front of the cache
        if len(cls.cache) > self.cache_size:
            cls.cache = cls.cache[-self.cache_size:]


class MessageNewHandler(BaseHandler, MessageMixin):
    @tornado.web.authenticated
    def post(self):
        timestamp = ''.join(str(time.time()).split('.'))[:11]
        message = {
            "id": str(uuid.uuid4()),
            "from": self.current_user,
            "body": self.get_argument("body"),
            "timestamp": timestamp,
        }
        message["html"] = self.render_string("message.html", message=message)
        if self.get_argument("next", None):
            self.redirect(self.get_argument("next"))
        else:
            self.write(message)
        self.new_messages([message])


class MessageUpdatesHandler(BaseHandler, MessageMixin):
    @tornado.web.authenticated
    @tornado.web.asynchronous
    def post(self):
        cursor = self.get_argument("cursor", None)
        self.wait_for_messages(self.async_callback(self.on_new_messages),
                               cursor=cursor)

    def on_new_messages(self, messages):
        # Closed client connection
        if self.request.connection.stream.closed():
            return
        self.finish(dict(messages=messages))


class AuthLoginHandler(BaseHandler):
    def get(self):
        self.write("""\
        <html>
         <body>
          <form action="/auth/login" method="post">
           Name: <input type="text" name="name">
           <input type="submit" value="Sign in">
          </form></body></html>""")

    def post(self):
        self.set_cookie("user", self.get_argument("name"))
        self.redirect("/")


class AuthLogoutHandler(BaseHandler):
    def get(self):
        self.clear_cookie("user")
        self.write("You are now logged out")


def main():
    tornado.options.parse_command_line()
    http_server = tornado.httpserver.HTTPServer(Application())
    http_server.listen(8888)
    tornado.ioloop.IOLoop.instance().start()


if __name__ == "__main__":
    main()
