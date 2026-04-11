import os
import datetime
from flask import Flask, render_template, request, redirect, url_for, jsonify
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
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
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


class StandupEntry(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    author     = db.Column(db.String(100), nullable=False)
    yesterday  = db.Column(db.Text, nullable=False)
    today      = db.Column(db.Text, nullable=False)
    blockers   = db.Column(db.Text, default='')
    entry_date = db.Column(db.Date, default=datetime.date.today)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Meeting(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    date       = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    notes      = db.relationship('MeetingNote', backref='meeting', lazy=True,
                                 cascade='all, delete-orphan', order_by='MeetingNote.created_at')
    actions    = db.relationship('ActionItem', backref='meeting', lazy=True,
                                 cascade='all, delete-orphan', order_by='ActionItem.id')


class MeetingNote(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'), nullable=False)
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class ActionItem(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    meeting_id = db.Column(db.Integer, db.ForeignKey('meeting.id'), nullable=False)
    text       = db.Column(db.String(300), nullable=False)
    assignee   = db.Column(db.String(100), default='')
    done       = db.Column(db.Boolean, default=False)


class Link(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    url         = db.Column(db.String(500), nullable=False)
    description = db.Column(db.Text, default='')
    category    = db.Column(db.String(100), default='General')
    created_at  = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Expense(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    description = db.Column(db.String(200), nullable=False)
    amount      = db.Column(db.Float, nullable=False)
    category    = db.Column(db.String(100), default='General')
    paid_by     = db.Column(db.String(100), default='')
    created_at  = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class Feedback(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    content    = db.Column(db.Text, nullable=False)
    category   = db.Column(db.String(50), default='General')
    resolved   = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class KanbanTask(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    title       = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default='')
    status      = db.Column(db.String(20), default='todo')   # todo | doing | done
    created_at  = db.Column(db.DateTime, default=datetime.datetime.utcnow)


class TeamMember(db.Model):
    id       = db.Column(db.Integer, primary_key=True)
    name     = db.Column(db.String(100), nullable=False)
    timezone = db.Column(db.String(100), nullable=False)
    role     = db.Column(db.String(100), default='')


class Availability(db.Model):
    id   = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    day  = db.Column(db.String(3), nullable=False)
    hour = db.Column(db.Integer, nullable=False)


class Article(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    title      = db.Column(db.String(200), nullable=False)
    category   = db.Column(db.String(100), default='General')
    content    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.datetime.utcnow)


with app.app_context():
    db.create_all()


# ── Routes ────────────────────────────────────────────────

@app.route('/')
def hub():
    return render_template('hub.html')


# ── Poll ──────────────────────────────────────────────────

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


# ── Daily Standup ─────────────────────────────────────────

@app.route('/standup')
def standup():
    today   = datetime.date.today()
    entries = StandupEntry.query.filter_by(entry_date=today).order_by(StandupEntry.created_at).all()
    return render_template('standup.html', entries=entries, today=today)


@app.route('/standup/post', methods=['POST'])
def post_standup():
    author    = request.form.get('author', '').strip()
    yesterday = request.form.get('yesterday', '').strip()
    today_txt = request.form.get('today', '').strip()
    blockers  = request.form.get('blockers', '').strip()
    if author and yesterday and today_txt:
        db.session.add(StandupEntry(
            author=author, yesterday=yesterday, today=today_txt, blockers=blockers))
        db.session.commit()
    return redirect(url_for('standup'))


# ── Meeting Notes ─────────────────────────────────────────

@app.route('/meeting-notes')
def meeting_notes():
    meetings = Meeting.query.order_by(Meeting.date.desc()).all()
    return render_template('meeting_notes.html', meetings=meetings)


@app.route('/meeting-notes/create', methods=['POST'])
def create_meeting():
    title = request.form.get('title', '').strip()
    date  = request.form.get('date', '').strip()
    if title and date:
        meeting = Meeting(title=title, date=date)
        db.session.add(meeting)
        db.session.commit()
        return redirect(url_for('meeting_detail', meeting_id=meeting.id))
    return redirect(url_for('meeting_notes'))


@app.route('/meeting-notes/<int:meeting_id>')
def meeting_detail(meeting_id):
    meeting = Meeting.query.get_or_404(meeting_id)
    return render_template('meeting_detail.html', meeting=meeting)


@app.route('/meeting-notes/<int:meeting_id>/add-note', methods=['POST'])
def add_note(meeting_id):
    content = request.form.get('content', '').strip()
    if content:
        db.session.add(MeetingNote(meeting_id=meeting_id, content=content))
        db.session.commit()
    return redirect(url_for('meeting_detail', meeting_id=meeting_id))


@app.route('/meeting-notes/<int:meeting_id>/add-action', methods=['POST'])
def add_action(meeting_id):
    text     = request.form.get('text', '').strip()
    assignee = request.form.get('assignee', '').strip()
    if text:
        db.session.add(ActionItem(meeting_id=meeting_id, text=text, assignee=assignee))
        db.session.commit()
    return redirect(url_for('meeting_detail', meeting_id=meeting_id))


@app.route('/meeting-notes/<int:meeting_id>/toggle-action/<int:action_id>', methods=['POST'])
def toggle_action(meeting_id, action_id):
    action = ActionItem.query.get_or_404(action_id)
    action.done = not action.done
    db.session.commit()
    return redirect(url_for('meeting_detail', meeting_id=meeting_id))


# ── Link Library ──────────────────────────────────────────

@app.route('/link-library')
def link_library():
    category = request.args.get('category', '')
    search   = request.args.get('q', '')
    q        = Link.query
    if category:
        q = q.filter_by(category=category)
    if search:
        q = q.filter(
            db.or_(Link.title.ilike(f'%{search}%'), Link.description.ilike(f'%{search}%')))
    links      = q.order_by(Link.created_at.desc()).all()
    categories = [c[0] for c in db.session.query(Link.category).distinct().all()]
    return render_template('link_library.html', links=links, categories=categories,
                           current_category=category, search=search)


@app.route('/link-library/add', methods=['POST'])
def add_link():
    title       = request.form.get('title', '').strip()
    url         = request.form.get('url', '').strip()
    description = request.form.get('description', '').strip()
    category    = request.form.get('category', 'General').strip() or 'General'
    if title and url:
        if not url.startswith(('http://', 'https://')):
            url = 'https://' + url
        db.session.add(Link(title=title, url=url, description=description, category=category))
        db.session.commit()
    return redirect(url_for('link_library'))


@app.route('/link-library/delete/<int:link_id>', methods=['POST'])
def delete_link(link_id):
    link = Link.query.get_or_404(link_id)
    db.session.delete(link)
    db.session.commit()
    return redirect(url_for('link_library'))


# ── Expense Tracker ───────────────────────────────────────

@app.route('/expense-tracker')
def expense_tracker():
    expenses = Expense.query.order_by(Expense.created_at.desc()).all()
    total    = sum(e.amount for e in expenses)
    by_cat   = {}
    for e in expenses:
        by_cat[e.category] = by_cat.get(e.category, 0) + e.amount
    return render_template('expense_tracker.html', expenses=expenses,
                           total=total, by_cat=by_cat)


@app.route('/expense-tracker/add', methods=['POST'])
def add_expense():
    description = request.form.get('description', '').strip()
    amount_str  = request.form.get('amount', '').strip()
    category    = request.form.get('category', 'General').strip() or 'General'
    paid_by     = request.form.get('paid_by', '').strip()
    try:
        amount = float(amount_str)
        if description and amount > 0:
            db.session.add(Expense(description=description, amount=amount,
                                   category=category, paid_by=paid_by))
            db.session.commit()
    except ValueError:
        pass
    return redirect(url_for('expense_tracker'))


@app.route('/expense-tracker/delete/<int:expense_id>', methods=['POST'])
def delete_expense(expense_id):
    expense = Expense.query.get_or_404(expense_id)
    db.session.delete(expense)
    db.session.commit()
    return redirect(url_for('expense_tracker'))


# ── Feedback Board ────────────────────────────────────────

@app.route('/feedback')
def feedback():
    show_resolved = request.args.get('show_resolved', '') == '1'
    q = Feedback.query
    if not show_resolved:
        q = q.filter_by(resolved=False)
    feedbacks = q.order_by(Feedback.resolved, Feedback.created_at.desc()).all()
    return render_template('feedback.html', feedbacks=feedbacks, show_resolved=show_resolved)


@app.route('/feedback/submit', methods=['POST'])
def submit_feedback():
    content  = request.form.get('content', '').strip()
    category = request.form.get('category', 'General').strip()
    if content:
        db.session.add(Feedback(content=content, category=category))
        db.session.commit()
    return redirect(url_for('feedback'))


@app.route('/feedback/resolve/<int:feedback_id>', methods=['POST'])
def resolve_feedback(feedback_id):
    fb = Feedback.query.get_or_404(feedback_id)
    fb.resolved = not fb.resolved
    db.session.commit()
    return redirect(url_for('feedback'))


# ── Kanban ────────────────────────────────────────────────

@app.route('/kanban')
def kanban():
    todo  = KanbanTask.query.filter_by(status='todo').order_by(KanbanTask.created_at).all()
    doing = KanbanTask.query.filter_by(status='doing').order_by(KanbanTask.created_at).all()
    done  = KanbanTask.query.filter_by(status='done').order_by(KanbanTask.created_at).all()
    return render_template('kanban.html', todo=todo, doing=doing, done=done)


@app.route('/kanban/add', methods=['POST'])
def add_task():
    title       = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    status      = request.form.get('status', 'todo')
    if title and status in ('todo', 'doing', 'done'):
        db.session.add(KanbanTask(title=title, description=description, status=status))
        db.session.commit()
    return redirect(url_for('kanban'))


@app.route('/kanban/move/<int:task_id>/<direction>', methods=['POST'])
def move_task(task_id, direction):
    task  = KanbanTask.query.get_or_404(task_id)
    order = ['todo', 'doing', 'done']
    idx   = order.index(task.status)
    if direction == 'forward' and idx < 2:
        task.status = order[idx + 1]
    elif direction == 'back' and idx > 0:
        task.status = order[idx - 1]
    db.session.commit()
    return redirect(url_for('kanban'))


@app.route('/kanban/delete/<int:task_id>', methods=['POST'])
def delete_task(task_id):
    task = KanbanTask.query.get_or_404(task_id)
    db.session.delete(task)
    db.session.commit()
    return redirect(url_for('kanban'))


# ── Timezone Buddy ────────────────────────────────────────

@app.route('/timezone')
def timezone():
    members = TeamMember.query.order_by(TeamMember.name).all()
    return render_template('timezone.html', members=members)


@app.route('/timezone/add', methods=['POST'])
def add_member():
    name      = request.form.get('name', '').strip()
    timezone_ = request.form.get('timezone', '').strip()
    role      = request.form.get('role', '').strip()
    if name and timezone_:
        db.session.add(TeamMember(name=name, timezone=timezone_, role=role))
        db.session.commit()
    return redirect(url_for('timezone'))


@app.route('/timezone/delete/<int:member_id>', methods=['POST'])
def delete_member(member_id):
    member = TeamMember.query.get_or_404(member_id)
    db.session.delete(member)
    db.session.commit()
    return redirect(url_for('timezone'))


# ── Availability Planner ──────────────────────────────────

AVAIL_DAYS  = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
AVAIL_HOURS = list(range(8, 18))


@app.route('/availability')
def availability():
    all_avail = Availability.query.all()
    heatmap   = {d: {h: 0 for h in AVAIL_HOURS} for d in AVAIL_DAYS}
    names_set = set()
    for a in all_avail:
        if a.day in heatmap and a.hour in heatmap[a.day]:
            heatmap[a.day][a.hour] += 1
        names_set.add(a.name)
    names     = sorted(names_set)
    max_count = max((heatmap[d][h] for d in AVAIL_DAYS for h in AVAIL_HOURS), default=1) or 1
    return render_template('availability.html', heatmap=heatmap, days=AVAIL_DAYS,
                           hours=AVAIL_HOURS, names=names, max_count=max_count)


@app.route('/availability/submit', methods=['POST'])
def submit_availability():
    name = request.form.get('name', '').strip()
    if name:
        Availability.query.filter_by(name=name).delete()
        for slot in request.form.getlist('slots'):
            parts = slot.split('-')
            if len(parts) == 2:
                day, hour_str = parts
                try:
                    hour = int(hour_str)
                    if day in AVAIL_DAYS and hour in AVAIL_HOURS:
                        db.session.add(Availability(name=name, day=day, hour=hour))
                except ValueError:
                    pass
        db.session.commit()
    return redirect(url_for('availability'))


@app.route('/availability/clear/<path:name>', methods=['POST'])
def clear_availability(name):
    Availability.query.filter_by(name=name).delete()
    db.session.commit()
    return redirect(url_for('availability'))


# ── Knowledge Base ────────────────────────────────────────

@app.route('/wiki')
def wiki():
    category = request.args.get('category', '')
    search   = request.args.get('q', '')
    q        = Article.query
    if category:
        q = q.filter_by(category=category)
    if search:
        q = q.filter(
            db.or_(Article.title.ilike(f'%{search}%'), Article.content.ilike(f'%{search}%')))
    articles   = q.order_by(Article.updated_at.desc()).all()
    categories = [c[0] for c in db.session.query(Article.category).distinct().all()]
    return render_template('wiki.html', articles=articles, categories=categories,
                           current_category=category, search=search)


@app.route('/wiki/new', methods=['GET', 'POST'])
def new_article():
    if request.method == 'POST':
        title    = request.form.get('title', '').strip()
        category = request.form.get('category', 'General').strip() or 'General'
        content  = request.form.get('content', '').strip()
        if title and content:
            article = Article(title=title, category=category, content=content)
            db.session.add(article)
            db.session.commit()
            return redirect(url_for('view_article', article_id=article.id))
    return render_template('wiki_article.html', article=None, editing=True)


@app.route('/wiki/<int:article_id>')
def view_article(article_id):
    article = Article.query.get_or_404(article_id)
    return render_template('wiki_article.html', article=article, editing=False)


@app.route('/wiki/<int:article_id>/edit', methods=['GET', 'POST'])
def edit_article(article_id):
    article = Article.query.get_or_404(article_id)
    if request.method == 'POST':
        article.title      = request.form.get('title', '').strip() or article.title
        article.category   = request.form.get('category', 'General').strip() or 'General'
        article.content    = request.form.get('content', '').strip() or article.content
        article.updated_at = datetime.datetime.utcnow()
        db.session.commit()
        return redirect(url_for('view_article', article_id=article.id))
    return render_template('wiki_article.html', article=article, editing=True)


@app.route('/wiki/<int:article_id>/delete', methods=['POST'])
def delete_article(article_id):
    article = Article.query.get_or_404(article_id)
    db.session.delete(article)
    db.session.commit()
    return redirect(url_for('wiki'))


# ── AI Chatbot ────────────────────────────────────────────

CHAT_SYSTEM_PROMPT = """You are a friendly, concise assistant built into the Broken Pickaxe Productivity Hub — a suite of 10 internal team tools built with Flask. Help users find features and get things done quickly.

Here is every app and how it works:

1. Team Poll (/poll) — Create a poll with a question and 2+ options. Others vote by clicking Vote. Results update live with progress bars.

2. Daily Standup (/standup) — Each morning, enter your name and fill in Yesterday / Today / Blockers. Everyone's updates for the current day appear as cards on the right.

3. Meeting Notes (/meeting-notes) — Create a meeting with a title and date, then open it to add bullet notes and action items. Action items can be assigned to a person and checked off when done.

4. Link Library (/link-library) — Save shared bookmarks with a title, URL, description, and category. Filter by category using the sidebar or search by keyword.

5. Expense Tracker (/expense-tracker) — Log expenses with description, amount, category, and who paid. A summary table shows totals per category and a grand total.

6. Feedback Board (/feedback) — Submit anonymous feedback tagged as Praise, Idea, Concern, or General. Anyone can mark items resolved. Use "Show Resolved" to see archived items.

7. Project Dashboard (/kanban) — A three-column kanban board: To Do, Doing, Done. Add tasks at the top, then move them forward or back with the arrow buttons. Delete when done.

8. Time Zone Buddy (/timezone) — Add team members by name, role, and timezone. Live clocks update automatically. Cards turn green when someone is within 9am–6pm local time.

9. Availability Planner (/availability) — Enter your name and click time slots on the Mon–Fri grid (8am–5pm) to mark when you're free. Submit to save. The heatmap on the right shows where the whole team overlaps — darker = more people available.

10. Knowledge Base (/wiki) — Write internal articles with a title, category, and plain-text content. Browse by category in the sidebar or search by keyword. Click any article to read it, then Edit or Delete from the article page.

Keep answers short and direct. Give step-by-step instructions when someone asks how to do something. If a question is unrelated to Broken Pickaxe, gently redirect back to the hub."""


@app.route('/chat', methods=['POST'])
def chat():
    data    = request.get_json(silent=True) or {}
    message = data.get('message', '').strip()
    history = data.get('history', [])

    if not message:
        return jsonify({'error': 'No message'}), 400

    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        return jsonify({'reply': (
            'The AI assistant isn\'t configured yet. '
            'Add your ANTHROPIC_API_KEY to the environment variables and restart the app.'
        )})

    try:
        from anthropic import Anthropic
        client   = Anthropic(api_key=api_key)
        messages = [{'role': m['role'], 'content': m['content']} for m in history]
        messages.append({'role': 'user', 'content': message})

        response = client.messages.create(
            model      = 'claude-haiku-4-5-20251001',
            max_tokens = 600,
            system     = CHAT_SYSTEM_PROMPT,
            messages   = messages,
        )
        return jsonify({'reply': response.content[0].text})
    except Exception as e:
        return jsonify({'reply': 'Sorry, something went wrong. Please try again.'}), 200


# ── Legacy redirect ───────────────────────────────────────

@app.route('/coming-soon/<slug>')
def coming_soon(slug):
    route_map = {
        'standup':         'standup',
        'meeting-notes':   'meeting_notes',
        'link-library':    'link_library',
        'expense-tracker': 'expense_tracker',
        'feedback':        'feedback',
        'kanban':          'kanban',
        'timezone':        'timezone',
        'availability':    'availability',
        'wiki':            'wiki',
    }
    if slug in route_map:
        return redirect(url_for(route_map[slug]))
    return render_template('coming_soon.html', app_name='This App')


if __name__ == '__main__':
    app.run(debug=True)
