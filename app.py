import os
from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# Use Azure PostgreSQL in production, SQLite locally
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
    'AZURE_POSTGRESQL_CONNECTIONSTRING', 'sqlite:///dev.db'
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.environ.get('SECRET_KEY', 'local-dev-key')

db = SQLAlchemy(app)


# ── Database Models ───────────────────────────────────────

class Poll(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    question   = db.Column(db.String(300), nullable=False)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
    options    = db.relationship('PollOption', backref='poll',
                                 lazy=True, cascade='all, delete-orphan')

    @property
    def total_votes(self):
        return sum(o.votes for o in self.options)


class PollOption(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('poll.id'), nullable=False)
    text    = db.Column(db.String(200), nullable=False)
    votes   = db.Column(db.Integer, default=0)

    def percentage(self, total):
        return round((self.votes / total) * 100) if total > 0 else 0


# Create tables if they don't exist
with app.app_context():
    db.create_all()


# ── Routes ────────────────────────────────────────────────

@app.route('/')
def hub():
    return render_template('hub.html')


@app.route('/poll')
def poll():
    polls = Poll.query.order_by(Poll.created_at.desc()).all()
    return render_template('poll.html', polls=polls)


@app.route('/poll/create', methods=['POST'])
def create_poll():
    question = request.form.get('question', '').strip()
    options  = [o.strip() for o in request.form.getlist('options') if o.strip()]
    if question and len(options) >= 2:
        new_poll = Poll(question=question)
        db.session.add(new_poll)
        db.session.flush()
        for text in options:
            db.session.add(PollOption(poll_id=new_poll.id, text=text))
        db.session.commit()
    return redirect(url_for('poll'))


@app.route('/poll/vote/<int:option_id>', methods=['POST'])
def vote(option_id):
    option = PollOption.query.get_or_404(option_id)
    option.votes += 1
    db.session.commit()
    return redirect(url_for('poll'))


@app.route('/coming-soon/<slug>')
def coming_soon(slug):
    names = {
        'standup':         'Daily Standup Board',
        'meeting-notes':   'Meeting Notes Hub',
        'link-library':    'Team Link Library',
        'expense-tracker': 'Office Expense Tracker',
        'feedback':        'Anonymous Feedback Board',
        'kanban':          'Project Status Dashboard',
        'timezone':        'Time Zone Buddy',
        'availability':    'Team Availability Planner',
        'wiki':            'Knowledge Base Wiki',
    }
    return render_template('coming_soon.html', app_name=names.get(slug, 'This App'))


if __name__ == '__main__':
    app.run(debug=True)
