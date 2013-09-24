#!/usr/bin/env python

"""
Simulates the ULTRACAM camera and dataservers
"""

import SimpleHTTPServer
import SocketServer
import logging
import cgi

PORT = 9980

class ServerHandler(SimpleHTTPServer.SimpleHTTPRequestHandler):

    def do_GET(self):
        logging.error(self.headers)
        SimpleHTTPServer.SimpleHTTPRequestHandler.do_GET(self)

    def do_POST(self):
        length = int(self.headers.getheader('content-length'))        
        sxml   = self.rfile.read(length)
        print 'xml =',sxml
        
        resp = """
<response>
<source>Camera server</source>
<status software="OK" camera="OK" />
<state camera="idle" />
</response>
"""
        self.send_response(200)
        self.send_header('Content-type', 'text/xml')
        self.end_headers()
        self.wfile.write(resp)

Handler = ServerHandler

httpd = SocketServer.TCPServer(("", PORT), Handler)

print "serving at port", PORT
httpd.serve_forever()
