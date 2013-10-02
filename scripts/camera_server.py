#!/usr/bin/env python

"""
Simulates the ULTRACAM camera and dataservers
"""

import SimpleHTTPServer
import SocketServer
import logging
import urlparse

PORT = 9980

post_resp = """
<response>
<source>Camera server</source>
<status software="OK" camera="OK" />
<state camera="idle" />
</response>
"""

get_resp = """
<response>
<command>%s</command>
<source>Camera server</source>
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
