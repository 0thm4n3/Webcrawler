import time
import sys
import os
import ssl
from socket import timeout as SocketTimeout
from socket import error as SocketError

# Import multi-threading modules
import Queue
import threading

# Import requests, to handle the get and post requests
try:

    import requests

except ImportError:
    print '[!]Could not import requests module'
    sys.exit()


from bs4 import BeautifulSoup, SoupStrainer
import uritools

requests.packages.urllib3.disable_warnings()


# Some necessary checks, to see if all the arguments are in order and the files exist
# Check if the required arguments exist
if len(sys.argv) != 5:
    print 'Usage: scanner.py site_list number_of_links output_file number_of_threads'
    print 'Example: scanner.py sites.txt 10 out.txt 25'
    sys.exit()

website_file = sys.argv[1]
links_n = sys.argv[2]
outfile = sys.argv[3]
threads_n = sys.argv[4]

# Make an integer from threads_n
try:
    threads_n = int(threads_n)

except ValueError:
    print '[!]Number of threads parameter is not a number!'
    sys.exit()

# Make an integer from links_n
try:
    links_n = int(links_n)

except ValueError:
    print '[!]Number of links parameter is not a number!'
    sys.exit()

# Check if the files exist.
for f in (website_file,):
    if not os.path.isfile(f):
        print '[!]File {0} not found!'.format(f)
        sys.exit()


def validate_link(href):
    """"""

    if href:

        o = uritools.urisplit(href)

        return o.query and o.scheme in (None, 'http', 'https')

    return False


def extract_links(data, add_queue, output_queue, thread_id, max_urls):
    """Retrieve a web page and parse max_urls links"""

    output_queue.put(('p', '[*]Thread-{0}:\tParsing: {1}'.format(thread_id, data)))

    try:

        response = requests.get(data,
                                verify=False,
                                timeout=2,
                                headers={"User-Agent": "Mozilla/5.0 (Windows NT 6.3; rv:36.0) Gecko/20100101 Firefox/36.0"})

    except (ssl.SSLError, requests.exceptions.RequestException, SocketError, SocketTimeout):
        pass

    else:

        if response.ok:
            parser = BeautifulSoup(response.text, 'html.parser', parse_only=SoupStrainer('a'))

            links = parser.findAll('a',
                                   {'href': validate_link},
                                   limit=max_urls)

            for link in links:
                found_url = uritools.urijoin(data, link['href'])

                output_queue.put(('w', found_url))

            return

    if not data.startswith('https://'):

        add_queue.put(data.replace('http://', 'https://'))


def run(site_q, thread_id, output_queue, shutdown_event, max_urls):
    """The main code, that each thread runs."""

    output_queue.put(('p', '[*]Thread-{0}:\tStarting'.format(thread_id)))

    while not shutdown_event.is_set():

        # The order of execution
        # Top first (the last step), bottom last(the first step)
        for get_queue, function, add_queue, args in ((site_q, extract_links, site_q, (max_urls, )),
                                                     ):

            try:

                data = get_queue.get(block=False)

            except Queue.Empty:
                pass

            else:

                function(data, add_queue, output_queue, thread_id, *args)
                get_queue.task_done()

    output_queue.put(('p', '[*]Thread-{0}:\tExiting'.format(thread_id)))
    return


def output_thread(output_queue, shutdown_event, output_file):
    """The thread that does the non thread-safe output
    (writing to a file and writing to stdout)."""

    sys.stdout.write('[+]Thread-OUT:\tStarting\n')

    while not shutdown_event.is_set():
        try:
            mode, message = output_queue.get(block=False)

        except Queue.Empty:
            pass

        else:

            message = message.encode('utf-8')
            # Print a message
            if mode == 'p':
                sys.stdout.write(message + '\n')

            # Write a message to the output file
            elif mode == 'w':
                with open(output_file, 'a') as hOut:
                    hOut.write(message + '\n')

            output_q.task_done()

    sys.stdout.write('[*]Thread-OUT:\tExiting\n')
    return


# The main part of the code
print '[*]Starting scanner!'
print '[*]Made by g0r and sc485'
start_time = time.time()

# Create queue objects
site_queue = Queue.Queue()

output_q = Queue.Queue()

shutdown = threading.Event()
output_shutdown = threading.Event()

# Read the hosts file, parse the domain
print '[*]Putting sites in queue.'
with open(website_file, 'r') as hInput:
    for line in hInput:

        url = line.strip()

        if '.' in url:

            if not line.startswith('http'):

                url = 'http://' + url

            site_queue.put(url)

total = site_queue.qsize()
if not total:
    print '[!]No sites found!'
    sys.exit()

print '[*]Found {} domains.'.format(total)

if total < threads_n:
    threads_n = total

print '[*]Starting {0} scanning threads.'.format(threads_n)
# Create threads_n threads and put them in a nice list to .join later
for i in xrange(threads_n):
    t = threading.Thread(target=run,
                         args=(site_queue, i + 1, output_q, shutdown, links_n))
    t.start()

print '[*]Starting output thread.'
t = threading.Thread(target=output_thread,
                     args=(output_q, output_shutdown, outfile))
t.start()

# Work down the queues until they are all empty.
site_queue.join()

shutdown.set()

# Write and print the last few messages and then exit
output_q.join()
output_shutdown.set()

sys.stdout.write('[+]Done! Time: {time:.2f} seconds.\n'.format(time=time.time() - start_time))
