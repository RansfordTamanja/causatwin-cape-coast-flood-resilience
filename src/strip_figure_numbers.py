import re

with open('plotting.py') as f:
    content = f.read()

new_content = re.sub(r'Figure \d+\. ', '', content)

with open('plotting.py', 'w') as f:
    f.write(new_content)

print('Done — removed all "Figure N." prefixes from plotting.py titles.')