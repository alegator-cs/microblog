from datetime import datetime
from flask import g, render_template, flash, redirect, url_for, request, jsonify, current_app
import sqlalchemy
from sqlalchemy import func
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from urllib.parse import urlparse as url_parse
from app import db
from app.main.forms import EditProfileForm, PostForm
from app.models import User, Post, Message, Notification, Task, Part, LegacyPart
from app.translate import translate
from app.main import bp
from app.main.forms import SearchForm, MessageForm

def is_absolute_url(next_page):
    return url_parse(next_page).netloc != ''

@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
        g.search_form = SearchForm()
    g.locale = str(get_locale())
    
@bp.route('/translate', methods = ['POST'])
@login_required
def translate_text():
    return jsonify({'text' : translate(request.form['text'],
                                       request.form['src_lang'],
                                       request.form['dst_lang'])})

@bp.route('/', methods = ['GET', 'POST'])
@bp.route('/index', methods = ['GET', 'POST'])
@login_required
def index():
    form = PostForm()
    if form.validate_on_submit():
        language = guess_language(form.post.data)
        if len(language) > 5 or language == 'UNKNOWN':
            language = ''
        post = Post(body = form.post.data, author = current_user, language = language)
        db.session.add(post)
        db.session.commit()
        flash(_('Post submitted'))
        return redirect(url_for('main.index'))

    page = request.args.get('page', 1, type = int)
    sql = sqlalchemy.select(Part, LegacyPart).join(LegacyPart)
    parts, legacy_parts = ((x,y) for x,y in db.session.execute(sql))

    # next_url = url_for('main.index', page = parts.next_num) if parts.has_next else None
    # prev_url = url_for('main.index', page = parts.prev_num) if parts.has_prev else None

    return render_template('index.html',
                           title = _('Home'),
                           form = form,
                           parts = parts,
                           legacy_parts = legacy_parts,
    )

@bp.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username = username).first_or_404()
    page = request.args.get('page', 1, type = int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
            page=page,
            per_page=current_app.config['POSTS_PER_PAGE'],
            error_out=False,
    )
    next_url = url_for('main.user', username = username, page = posts.next_num) \
        if posts.has_next else None
    prev_url = url_for('main.user', username = username, page = posts.prev_num) \
        if posts.has_prev else None
    return render_template(
            'user.html',
            title = _('Profile'),
            user = user,
            posts = posts.items,
            next_url = next_url,
            prev_url = prev_url,
    )

@bp.route('/add_part', methods = ['GET', 'POST'])
@login_required
def add_part(name, desc, img_url):
  id = legacy_db.session.query(func.max(Part.id)).scalar()
  p = Part(id=id, name=name, desc=desc, img_url=img_url)
  legacy_db.session.add(p)
  legacy_db.session.commit()

@bp.route('/edit_profile', methods = ['GET', 'POST'])
@login_required
def edit_profile():
    form = EditProfileForm(current_user.username)
    if form.validate_on_submit():
        current_user.username = form.username.data
        current_user.about_me = form.about_me.data
        db.session.commit()
        flash(_('Profile saved'))
        return redirect(url_for('main.index'))
    elif request.method == 'GET':
        form.username.data = current_user.username
        form.about_me.data = current_user.about_me
    return render_template('edit_profile.html', title = _('Edit Profile'), form = form)

@bp.route('/follow/<username>')
@login_required
def follow(username):
    user = User.query.filter_by(username = username).first()
    if user is None:
        # flash('User {} not found.'.format(username))
        flash(_('User %(username)s not found.', username = username))
        return redirect(url_for('main.index'))
    if user == current_user:
        flash(_('Cannot follow self.'))
        return redirect(url_for('main.user', username = username))
    current_user.follow(user)
    db.session.commit()
    # flash('{} followed.'.format(username))
    flash(_('%(username)s followed.', username = username))
    return redirect(url_for('main.user', username = username))

@bp.route('/unfollow/<username>')
@login_required
def unfollow(username):
    user = User.query.filter_by(username = username).first()
    if user is None:
        flash(_('User %(username)s not found.', username = username))
        return redirect(url_for('main.index'))
    if user == current_user:
        flash(_('Cannot unfollow self.'))
        return redirect(url_for('main.user', username = username))
    current_user.unfollow(user)
    db.session.commit()
    # flash('{} unfollowed.'.format(username))
    flash(_('%(username)s unfollowed.', username = username))
    return redirect(url_for('main.user', username = username))

@bp.route('/explore')
@login_required
def explore():
    page = request.args.get('page', 1, type = int)
    posts = Post.query.order_by(Post.timestamp.desc()).paginate(
            page = page,
            per_page = current_app.config['POSTS_PER_PAGE'],
            error_out = False,
    )
    next_url = url_for('main.explore', page = posts.next_num) if posts.has_next else None
    prev_url = url_for('main.explore', page = posts.prev_num) if posts.has_prev else None
    return render_template(
            'index.html',
            title = _('Home'),
            posts = posts.items,
            next_url = next_url,
            prev_url = prev_url,
    )

@bp.route('/search')
@login_required
def search():
    if not g.search_form.validate():
        return
    page = request.args.get('page', 1, type = int)
    posts, total = Post.search(g.search_form.query.data, page,
                               current_app.config['POSTS_PER_PAGE'])
    next_url = url_for('main.search', query = g.search_form.query.data, page = page + 1) \
        if total > page * current_app.config['POSTS_PER_PAGE'] else None
    prev_url = url_for('main.search', query = g.search_form.query.data, page = page - 1) \
        if page > 1 else None
    return render_template('search.html', title = _('Search'), posts = posts,
                           next_url = next_url, prev_url = prev_url)

@bp.route('/user/<username>/popup')
@login_required
def user_popup(username):
    user = User.query.filter_by(username = username).first_or_404()
    return render_template('user_popup.html', user = user)

@bp.route('/send_message/<recipient>', methods = ['GET', 'POST'])
@login_required
def send_message(recipient):
    user = User.query.filter_by(username = recipient).first_or_404()
    form = MessageForm()
    if form.validate_on_submit():
        msg = Message(
            author = current_user,
            recipient = user,
            body = form.message.data,
        )
        db.session.add(msg)
        user.add_notification('unread_message_count', user.get_new_message_count())
        db.session.commit()
        flash(_('Message sent.'))
        return redirect(url_for('main.user', username = recipient))
    return render_template(
        'send_message.html',
        title = _('Send'),
        form = form,
        recipient = recipient,
    )

@bp.route('/messages')
@login_required
def messages():
    current_user.last_message_read_time = datetime.utcnow()
    current_user.add_notification('unread_message_count', 0)
    db.session.commit()
    page = request.args.get('page', 1, type = int)
    messages = current_user.messages_received.order_by(
        Message.timestamp.desc()).paginate(
            page,
            current_app.config['POSTS_PER_PAGE'],
            False,
        )
    next_url = url_for('main.messages', page = messages.next_num) \
        if messages.has_next else None
    prev_url = url_for('main.messages', page = messages.prev_num) \
        if messages.has_prev else None
    return render_template(
        'messages.html',
        messages = messages.items,
        next_url = next_url,
        prev_url = prev_url,
    )

@bp.route('/notifications')
@login_required
def notifications():
    since = request.args.get('since', 0.0, type = float)
    notifications = current_user.notifications.filter(
        Notification.timestamp > since).order_by(
            Notification.timestamp.asc())
    return jsonify([{
        'name' : n.name,
        'data' : n.get_data(),
        'timestamp' : n.timestamp,
    } for n in notifications])

@bp.route('/export_posts')
@login_required
def export_posts():
    if current_user.get_tasks(name = 'export_posts', complete = False):
        flash(_('Export already in progress.'))
    else:
        current_user.launch_task('export_posts', _('Export in progress.'))
        db.session.commit()
    return redirect(url_for('main.user', username = current_user.username))
