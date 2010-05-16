import os

import tornado.httpserver
import tornado.ioloop
import tornado.web

from pyhbase import HBaseConnection

class HBaseTable(object):
  def __init__(self, name):
    self._name = name
    self._conn = HBaseConnection('localhost', 9090)

  def get_column_families(self):
    column_descriptors = self._conn.client.getColumnDescriptors(self.name)
    return [cd for cd in column_descriptors.values()]

  def get_regions(self):
    regions = self._conn.client.getTableRegions(self.name)
    return regions
  
  # read-only properties
  name = property(lambda self: self._name)
  column_families = property(lambda self: self.get_column_families())
  regions = property(lambda self: self.get_regions())

class MainHandler(tornado.web.RequestHandler):
  def get(self):
    conn = HBaseConnection('localhost', 9090)
    tables = [HBaseTable(t) for t in conn.client.getTableNames()]
    self.render("index.html", tables=tables)

settings = {
  "static_path": os.path.join(os.path.dirname(__file__), "static"),
  "template_path": os.path.join(os.path.dirname(__file__), "templates"),
}

application = tornado.web.Application([
  (r"/", MainHandler),
], **settings)

if __name__ == "__main__":
  http_server = tornado.httpserver.HTTPServer(application)
  http_server.listen(8888)
  tornado.ioloop.IOLoop.instance().start()
