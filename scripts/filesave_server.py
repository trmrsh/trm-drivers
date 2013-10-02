#!/usr/bin/env python

"""
Simulates the ULTRACAM camera and dataservers
"""

import SimpleHTTPServer
import SocketServer
import logging
import urlparse

PORT = 9981

post_resp = """
<response>
<source>Filesave data handler</source>
<status software="OK" />
<state server="idle" />
<lastfile path="run003" />
</response>
"""

get_resp = """
<response>
<command>%s</command>
<source>Filesave data handler</source>
<status software="OK" camera="OK" />
<state camera="idle" />
</response>
"""

class ServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def do_GET(self):
        parsed_path = urlparse.urlparse(self.path)
        self.send_response(200)
        self.send_header('Content-type', 'text/xml')
        self.end_headers()
        self.wfile.write(get_resp % (parsed_path.query,))
        logging.error(self.headers)
        SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        length = int(self.headers.getheader('content-length'))        
        sxml   = self.rfile.read(length)
        print 'xml =',sxml

        self.send_response(200)
        self.send_header('Content-type', 'text/xml')
        self.end_headers()
        self.wfile.write(post_resp)

Handler = ServerHandler

httpd = SocketServer.TCPServer(("", PORT), Handler)

print "serving at port", PORT
httpd.serve_forever()
