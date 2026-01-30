from flask import Flask, render_template_string
from db import get_all

app = Flask(__name__)

TEMPLATE = """
<h1>X Handle Monitor</h1>
<table border="1">
<tr>
<th>Handle</th>
<th>Latest Post</th>
<th>Time</th>
<th>Last Checked</th>
</tr>
{% for row in rows %}
<tr>
<td>{{row[0]}}</td>
<td>{{row[2]}}</td>
<td>{{row[3]}}</td>
<td>{{row[4]}}</td>
</tr>
{% endfor %}
</table>
"""

@app.route("/")
def index():
    rows = get_all()
    return render_template_string(TEMPLATE, rows=rows)

def run_dashboard():
    app.run(port=5000)

