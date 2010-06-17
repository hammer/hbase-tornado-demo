#! /usr/bin/env python

from pyhbase.connection import HBaseConnection

if __name__ == "__main__":
  hbase_conn = HBaseConnection('localhost', 9090)
  if not hbase_conn.table_exists('message_log'):
    hbase_conn.create_table('message_log', 'messages')
