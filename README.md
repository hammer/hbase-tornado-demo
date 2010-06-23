A demonstration of [HBase](http://hbase.org) and [Tornado](http://www.tornadoweb.org).

Adds new features to the chat demo:

1. Persist chat messages to HBase
1. Post to chat room with curl

     $ curl --data-urlencode "body=whatever i like" -b "user=Script" http://mysweetchatserver.com/a/message/new

Upcoming features:

1. Bots
1. Channels

