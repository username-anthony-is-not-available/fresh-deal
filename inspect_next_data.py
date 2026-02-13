
from bs4 import BeautifulSoup
import json

with open('/tmp/maxi_debug.html', 'r') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

next_data = soup.find('script', id='__NEXT_DATA__')
if next_data:
    print("Found __NEXT_DATA__")
    data = json.loads(next_data.string)
    # Save a slice of it to inspect
    with open('next_data_slice.json', 'w') as f:
        json.dump(data, f, indent=2)
    print("Saved next_data_slice.json")
else:
    print("__NEXT_DATA__ not found")
