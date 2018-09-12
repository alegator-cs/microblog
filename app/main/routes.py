from datetime import datetime
from flask import g, render_template, flash, redirect, url_for, request, jsonify
from flask_login import current_user, login_required
from flask_babel import _, get_locale
from guess_language import guess_language
from werkzeug.urls import url_parse
from app import app, db
from app.main.forms import EditProfileForm, PostForm
from app.models import User, Post
from app.translate import translate
from app.main import bp

def is_absolute_url(next_page):
    return url_parse(next_page).netloc != ''

@bp.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()
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
    posts = current_user.followed_posts().order_by(Post.timestamp.desc()).paginate(
            page,
            app.config['POSTS_PER_PAGE'],
            False
    )
    next_url = url_for('main.index', page = posts.next_num) if posts.has_next else None
    prev_url = url_for('main.index', page = posts.prev_num) if posts.has_prev else None
    return render_template(
            'index.html',
            title = _('Home'),
            form = form,
            posts = posts.items,
            next_url = next_url,
            prev_url = prev_url,
    )

@bp.route('/user/<username>')
@login_required
def user(username):
    user = User.query.filter_by(username = username).first_or_404()
    page = request.args.get('page', 1, type = int)
    posts = user.posts.order_by(Post.timestamp.desc()).paginate(
            page,
            app.config['POSTS_PER_PAGE'],
            False,
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
            page,
            app.config['POSTS_PER_PAGE'],
            False,
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