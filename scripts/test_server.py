#!/usr/bin/env python
#
# This imitates the server that runs in usdriver to send window data off to
# rplot (runs on socket 5100).
#
# To test this, you need to switch off the genuine server designed for this
# purpose inside usdriver.

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer
import os

# Create custom HTTPRequestHandler class
class KodeFunHTTPRequestHandler(BaseHTTPRequestHandler):

    # handle GET command
    def do_GET(self):

        #send code 200 response
        self.send_response(200)

        #send header first
        #            self.send_header('Content-type','text-html')
        self.send_header('Content-type','text/plain')
        self.end_headers()

        #send file content to client
        self.wfile.write("""
2 2 2
101 101 200 200
201 501 200 250
""")

def run():
    print('Test usdriver http server is starting...')

    # ip and port of server
    server_address = ('localhost', 5100)
    httpd = HTTPServer(server_address, KodeFunHTTPRequestHandler)
    print('Test usdriver http server is running...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
