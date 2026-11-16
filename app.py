import sqlite3
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'kunci_rahasia_perpustakaan_hijau'
DATABASE = 'perpustakaan.db'


def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


# Decorator untuk otorisasi login dan role
def login_required(role=None):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'user_id' not in session:
                flash('Silakan login terlebih dahulu.', 'warning')
                return redirect(url_for('login'))
            if role and session.get('role') != role:
                flash('Anda tidak memiliki akses ke halaman ini.', 'danger')
                return redirect(url_for('katalog'))
            return f(*args, **kwargs)

        return decorated_function

    return decorator


# --- AUTENTIKASI ---

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()

        if user and check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['nama'] = user['nama']
            session['role'] = user['role']
            flash(f'Selamat datang kembali, {user["nama"]}!', 'success')

            if user['role'] == 'pustakawan':
                return redirect(url_for('kelola_buku'))
            return redirect(url_for('katalog'))

        flash('Username atau password tidak sesuai.', 'danger')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        nama = request.form['nama'].strip()
        username = request.form['username'].strip()
        password = request.form['password']

        conn = get_db()
        try:
            hashed_pw = generate_password_hash(password)
            conn.execute(
                'INSERT INTO users (nama, username, password, role) VALUES (?, ?, ?, ?)',
                (nama, username, hashed_pw, 'peminjam')
            )
            conn.commit()
            flash('Pendaftaran akun berhasil. Silakan login.', 'success')
            return redirect(url_for('login'))
        except sqlite3.IntegrityError:
            flash('Username sudah digunakan. Silakan gunakan yang lain.', 'danger')
        finally:
            conn.close()

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('Anda telah keluar dari sistem.', 'info')
    return redirect(url_for('login'))


# --- FITUR PEMINJAM (ANGGOTA) ---

@app.route('/')
@login_required()
def katalog():
    conn = get_db()
    buku_list = conn.execute('SELECT * FROM buku ORDER BY judul ASC').fetchall()
    conn.close()
    return render_template('katalog.html', buku_list=buku_list)


@app.route('/pinjam/<int:buku_id>', methods=['POST'])
@login_required(role='peminjam')
def pinjam_buku(buku_id):
    user_id = session['user_id']
    conn = get_db()

    buku = conn.execute('SELECT * FROM buku WHERE id = ?', (buku_id,)).fetchone()
    if not buku or buku['stok_tersedia'] <= 0:
        flash('Buku tidak tersedia untuk dipinjam.', 'danger')
        conn.close()
        return redirect(url_for('katalog'))

    # Cek apakah user sedang meminjam buku yang sama dan belum dikembalikan
    sedang_pinjam = conn.execute(
        'SELECT id FROM peminjaman WHERE user_id = ? AND buku_id = ? AND status = "dipinjam"',
        (user_id, buku_id)
    ).fetchone()

    if sedang_pinjam:
        flash('Anda sedang meminjam buku ini. Selesaikan peminjaman sebelumnya terlebih dahulu.', 'warning')
        conn.close()
        return redirect(url_for('katalog'))

    # Catat peminjaman dan kurangi stok
    conn.execute('INSERT INTO peminjaman (user_id, buku_id) VALUES (?, ?)', (user_id, buku_id))
    conn.execute('UPDATE buku SET stok_tersedia = stok_tersedia - 1 WHERE id = ?', (buku_id,))
    conn.commit()
    conn.close()

    flash(f'Berhasil meminjam buku: {buku["judul"]}', 'success')
    return redirect(url_for('pinjaman_saya'))


@app.route('/pinjaman-saya')
@login_required(role='peminjam')
def pinjaman_saya():
    conn = get_db()
    pinjaman = conn.execute('''
                            SELECT p.id, b.judul, b.penulis, p.tanggal_pinjam, p.tanggal_kembali, p.status
                            FROM peminjaman p
                                     JOIN buku b ON p.buku_id = b.id
                            WHERE p.user_id = ?
                            ORDER BY p.id DESC
                            ''', (session['user_id'],)).fetchall()
    conn.close()
    return render_template('pinjaman_saya.html', pinjaman=pinjaman)


# --- FITUR PUSTAKAWAN ---

@app.route('/kelola-buku', methods=['GET', 'POST'])
@login_required(role='pustakawan')
def kelola_buku():
    conn = get_db()
    if request.method == 'POST':
        judul = request.form['judul'].strip()
        penulis = request.form['penulis'].strip()
        kategori = request.form['kategori'].strip()
        stok = int(request.form['stok'])

        conn.execute(
            'INSERT INTO buku (judul, penulis, kategori, stok_total, stok_tersedia) VALUES (?, ?, ?, ?, ?)',
            (judul, penulis, kategori, stok, stok)
        )
        conn.commit()
        flash('Buku baru berhasil ditambahkan ke katalog.', 'success')

    buku_list = conn.execute('SELECT * FROM buku ORDER BY id DESC').fetchall()
    conn.close()
    return render_template('kelola_buku.html', buku_list=buku_list)


@app.route('/kelola-buku/hapus/<int:buku_id>', methods=['POST'])
@login_required(role='pustakawan')
def hapus_buku(buku_id):
    conn = get_db()
    # Cek apakah buku sedang dipinjam
    aktif = conn.execute('SELECT id FROM peminjaman WHERE buku_id = ? AND status = "dipinjam"', (buku_id,)).fetchone()
    if aktif:
        flash('Buku tidak dapat dihapus karena sedang dalam status dipinjam.', 'danger')
    else:
        conn.execute('DELETE FROM buku WHERE id = ?', (buku_id,))
        conn.commit()
        flash('Buku berhasil dihapus dari sistem.', 'success')
    conn.close()
    return redirect(url_for('kelola_buku'))


@app.route('/kelola-pinjaman')
@login_required(role='pustakawan')
def kelola_pinjaman():
    conn = get_db()
    daftar_pinjam = conn.execute('''
                                 SELECT p.id,
                                        u.nama AS nama_peminjam,
                                        b.judul,
                                        p.tanggal_pinjam,
                                        p.tanggal_kembali,
                                        p.status,
                                        p.buku_id
                                 FROM peminjaman p
                                          JOIN users u ON p.user_id = u.id
                                          JOIN buku b ON p.buku_id = b.id
                                 ORDER BY p.status DESC, p.id DESC
                                 ''').fetchall()
    conn.close()
    return render_template('kelola_pinjaman.html', pinjaman=daftar_pinjam)


@app.route('/kembalikan-buku/<int:pinjam_id>', methods=['POST'])
@login_required(role='pustakawan')
def verifikasi_kembali(pinjam_id):
    conn = get_db()
    pinjam = conn.execute('SELECT * FROM peminjaman WHERE id = ?', (pinjam_id,)).fetchone()

    if pinjam and pinjam['status'] == 'dipinjam':
        conn.execute(
            'UPDATE peminjaman SET status = "dikembalikan", tanggal_kembali = CURRENT_DATE WHERE id = ?',
            (pinjam_id,)
        )
        conn.execute('UPDATE buku SET stok_tersedia = stok_tersedia + 1 WHERE id = ?', (pinjam['buku_id'],))
        conn.commit()
        flash('Status buku berhasil diubah menjadi dikembalikan dan stok diperbarui.', 'success')

    conn.close()
    return redirect(url_for('kelola_pinjaman'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)