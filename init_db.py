import sqlite3
from werkzeug.security import generate_password_hash

DATABASE_NAME = 'perpustakaan.db'

def get_db():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    cursor = conn.cursor()

    # 1. Tabel Users
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nama TEXT NOT NULL,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('pustakawan', 'peminjam'))
        )
    ''')

    # 2. Tabel Buku
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS buku (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            judul TEXT NOT NULL,
            penulis TEXT NOT NULL,
            kategori TEXT NOT NULL,
            stok_total INTEGER NOT NULL,
            stok_tersedia INTEGER NOT NULL
        )
    ''')

    # 3. Tabel Transaksi Peminjaman
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS peminjaman (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            buku_id INTEGER NOT NULL,
            tanggal_pinjam DATE DEFAULT (CURRENT_DATE),
            tanggal_kembali DATE,
            status TEXT NOT NULL DEFAULT 'dipinjam' CHECK(status IN ('dipinjam', 'dikembalikan')),
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (buku_id) REFERENCES buku (id)
        )
    ''')

    # Akun default pustakawan: username 'admin', password 'admin123'
    cursor.execute("SELECT id FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        hashed_pw = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (nama, username, password, role) VALUES (?, ?, ?, ?)",
            ('Kepala Pustakawan', 'admin', hashed_pw, 'pustakawan')
        )

    # Tambah contoh buku jika katalog kosong
    cursor.execute("SELECT COUNT(*) FROM buku")
    if cursor.fetchone()[0] == 0:
        buku_sampel = [
            ('Clean Code', 'Robert C. Martin', 'Teknologi', 5, 5),
            ('Laskar Pelangi', 'Andrea Hirata', 'Sastra', 4, 4),
            ('Filosofi Teras', 'Henry Manampiring', 'Pengembangan Diri', 3, 3)
        ]
        cursor.executemany(
            "INSERT INTO buku (judul, penulis, kategori, stok_total, stok_tersedia) VALUES (?, ?, ?, ?, ?)",
            buku_sampel
        )

    conn.commit()
    conn.close()
    print("Database perpustakaan.db berhasil diinisialisasi.")

if __name__ == '__main__':
    init_db()